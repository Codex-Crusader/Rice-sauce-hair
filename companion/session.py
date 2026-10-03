"""The session: one worker thread, one queue, all conversation state, and the flow of one request.

  ui -> session -> context.snapshot()
                -> planner.route() / planner.plan()  -> Decision
                -> policy.decide()                   -> Verdict
                -> tools / handoff                   -> Result
                -> voice.speak()                     -> reply to the ui
                -> store                             (chat, memory, mood)

The UI puts events in the queue (send, answer, remark). The worker takes them one at a time.
Callbacks (on_reply, on_state, on_question) come from the worker thread; the UI must hand them
to the GTK main loop.
"""
import logging
import queue
import re
import threading
import time
import urllib.error
from dataclasses import dataclass, field

import candidates
import context
import handoff
import planner
import policy
import tools as toolbox
import voice
from mood import Mood
from runner import Result, Runner
from store import Store

log = logging.getLogger("session")
YES, NO = ("yes", "y", "ok", "okay", "sure", "do it"), ("no", "n", "nope", "don't", "stop")
HISTORY_LIMIT = 64  # chat messages kept (the model sees fewer)
# Tools that act on one tab or window, and the argument that names it: what "it" means next time
# "bring up my editor": she means the open window, not a new one
BRING_UP = re.compile(r"\b(bring up|show me|switch to|go to|go back to|back to|focus|pull up)\b", re.I)
TARGET_ARGS = {"tell_claude": ("claude", "message"), "web_search": ("tab", "query"), "switch_tab": ("tab", "tab"),
               "open_tab": ("tab", "url"), "open_url": ("tab", "url"), "focus_window": ("window", "window"),
               "open_app": ("window", "name")}


@dataclass
class Work:
    """One request while it runs: what she tried and what came back."""
    request: str
    snap: object                                  # the context.Snapshot taken for this request (or None)
    results: list = field(default_factory=list)   # (tool name, args, Result)
    rounds: int = 1                               # plan calls made for this request
    candidates: list = field(default_factory=list)  # the best matches for the request (candidates.find)

    @property
    def screen(self):
        """The snapshot as the context message for the plan call."""
        return self.snap.message() if self.snap else {"role": "tool", "tool_name": "screen", "content": ""}

    def failures(self):
        """Real failures: not a clear answer (not found, refused, the user said no)."""
        return [r for _, _, r in self.results if not r.ok and not r.final]

    def messages(self):
        """The results as tool-role messages, for a second plan call."""
        return [{"role": "tool", "tool_name": name,
                 "content": f"{name}({args}) -> {'ok' if r.ok else 'FAILED'}: {r.text[:300]}"}
                for name, args, r in self.results]


@dataclass
class Question:
    """A yes/no question that waits for the user. The steps after it wait in rest."""
    tool: object
    args: dict
    rest: list
    work: Work
    text: str


@dataclass
class State:
    history: list = field(default_factory=list)
    question: Question = None   # the open yes/no question, or None
    last_target: tuple = None   # (kind, word) of the last tab or window she acted on
    last_text: str = ""         # the user's message of the current request
    cancelled: bool = False     # set by cancel(); the flow stops before the next step


@dataclass
class UserMessage:
    text: str


@dataclass
class Answer:
    yes: bool


@dataclass
class HandoffDone:
    """Path A finished in its own thread: Claude Code's answer, to speak."""
    work: Work
    task: str
    result: Result


@dataclass
class Remark:
    event: str
    must_say: bool = False  # a scan result: wait until she is free, and keep it in the chat


class Session:
    def __init__(self, config, chrome, on_reply, on_state, on_question, runner=None, options=None):
        self.config = config
        self.options = options  # extra model options (the eval sets a seed)
        self.runner = runner or Runner()
        self.store = Store(config)
        self.tools = toolbox.build_tools(chrome, self.runner, config, self.store)
        self.mood = Mood(self.store, config.user, config.persona.get("moods"))
        self.state = State(history=list(self.mood.history()))  # the chat continues after a restart
        self.on_reply, self.on_state, self.on_question = on_reply, on_state, on_question
        self.queue = queue.Queue()
        self.busy = False
        threading.Thread(target=self._work, daemon=True).start()

    # ----- called from the UI thread -----

    def send(self, text):
        """A typed message. "yes" or "no" while a question is open is the answer."""
        word = text.strip().lower().rstrip(".!")
        if self.state.question and word in YES + NO:
            self.answer(word in YES)
        else:
            self.queue.put(UserMessage(text))

    def answer(self, yes):
        self.queue.put(Answer(yes))

    def remark(self, event, must_say=False):
        """Speak on her own. A normal remark is dropped when she is busy or a question is open."""
        if not must_say and (self.busy or not self.queue.empty() or self.state.question):
            return
        self.queue.put(Remark(event, must_say))

    def cancel(self):
        """Stop: drop the open question and the waiting events. The current model call ends first."""
        self.state.cancelled = True
        self.state.question = None
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def asking(self):
        return self.state.question is not None

    # ----- the worker thread -----

    def _work(self):
        while True:
            event = self.queue.get()
            self.busy = True
            try:
                self._handle(event)
            except urllib.error.HTTPError as e:
                reason = "my model is not downloaded yet" if e.code == 404 else f"Ollama answered {e.code}"
                self.on_reply("worried", f"I cannot think clearly yet: {reason}.")
            except urllib.error.URLError:
                self.on_reply("worried", "I cannot reach my thoughts right now. Is the Ollama service running?")
            except Exception as e:  # never let the worker die on a bad reply
                log.exception("error in %s", type(event).__name__)
                self.on_reply("worried", f"Something went wrong inside me: {e}")
            finally:
                self.busy = False

    def _handle(self, event):
        if isinstance(event, UserMessage):
            self._request(event.text)
        elif isinstance(event, Answer):
            question, self.state.question = self.state.question, None
            if question:
                self.state.cancelled = False
                self._answered(question, event.yes)
        elif isinstance(event, HandoffDone):
            if self.state.question:  # do not hide the Yes and No buttons: say it a little later
                threading.Timer(10, self.queue.put, (event,)).start()
                return
            event.work.results.append(("handoff", {"task": event.task}, event.result))
            if event.result.ok:
                answer = f"{context.LABEL}\n{event.result.text[:2000]}"
                self._say(f"(Claude Code answered the question you handed over ({event.task}):\n{answer}\n"
                          f"Tell {self.config.user} the answer in your voice, in one to three short sentences.)",
                          event.work)
            else:
                self._say(f"(You asked Claude Code, but it did not work: {event.result.text}\n"
                          f"Tell {self.config.user} plainly, in one or two short sentences.)", event.work)
        elif isinstance(event, Remark):
            if self.state.question:  # a remark would hide the Yes and No buttons
                if event.must_say:
                    threading.Timer(20, self.remark, (event.event, True)).start()
                return
            self.on_state("thinking")
            self._say(f"(This is not a message from {self.config.user}. Event: {event.event}. "
                      f"Say one short, natural line in character.)", keep=event.must_say)

    # ----- the flow of one request -----

    def _request(self, text):
        st = self.state
        st.question, st.cancelled, st.last_text = None, False, text  # a new request drops an open question
        log.info("%s: %r", self.config.user, text)
        self.mood.note_user(text)
        st.history.append({"role": "user", "content": text})
        self.on_state("thinking")
        request = self._corrected(text)
        work = Work(request, context.snapshot(self.tools, self.runner, st.last_target))
        learned = self.store.aliases()
        strict = lambda name: toolbox.find_app(name, fuzzy=False, learned=learned)  # the router: exact matches only
        decision = planner.route(request, strict, {**toolbox.APP_ALIASES, **learned})
        if decision is None:
            work.candidates = candidates.find(request, work.snap, self.runner, learned)
            log.info("candidates: %s", [c.label for c in work.candidates])
            decision = self._plan(work)
        self._carry_out(decision, work)

    def _plan(self, work):
        return planner.plan(self.config.model, work.request, self.tools, self.state.history[:-1], work.screen,
                            toolbox.app_names(), earlier=work.messages(), options=self.options,
                            candidates=work.candidates)

    def _corrected(self, text):
        """ "no, I meant PyCharm" after a wrong guess: learn that the words of the last request mean
        PyCharm, and do the last request again with that meaning. Other text comes back unchanged."""
        m = planner.CORRECTION.match(text)
        earlier = [h["content"] for h in self.state.history[:-1] if h["role"] == "user"]
        if not m or not earlier:
            return text
        what, previous = m.group("what").strip(), earlier[-1]
        words = " ".join(candidates.words_of(previous))
        if words and toolbox.find_app(what, fuzzy=False):  # only names of installed apps are learned
            self.store.learn(words, what)
            log.info("learned: %r means %r", words, what)
        return f"{previous} (I meant {what})"

    def _carry_out(self, decision, work):
        log.info("decision %s (%s): %s", decision.kind, decision.source,
                 [(s.tool, s.args) for s in decision.steps] or decision.text)
        if decision.kind == "do":
            done = [(n, a) for n, a, r in work.results if r.ok]
            steps = [self._prefer_open_window(s, work) for s in decision.steps]
            steps = [s for s in steps if (s.tool, s.args) not in done]  # never run a done step again
            if steps:
                self._run_steps(steps, work)
            else:
                self._say(self._results_note(work), work)
        elif decision.kind == "handoff":
            self._hand_off(decision.text or work.request, work, decision.source)
        elif decision.kind == "ask":
            self._say(f'(Ask {self.config.user} this, in one short line, in your voice: "{decision.text}")', work)
        else:
            note = f"({decision.text})" if decision.text else f"(Answer {self.config.user} in your voice.)"
            self._say(note, work)

    def _prefer_open_window(self, step, work):
        """ "Bring up X": focus the open window of app X instead of opening X again."""
        if step.tool != "open_app" or not BRING_UP.search(work.request):
            return step
        app = toolbox.find_app(str(step.args.get("name", "")))
        for c in work.candidates:
            if c.step.tool == "focus_window":
                window_app = toolbox.find_app(c.step.args["window"])
                if app and window_app and window_app[1][0] == app[1][0]:
                    log.info("open %s -> focus its open window", step.args.get("name"))
                    return c.step
        return step

    def _run_steps(self, steps, work):
        for i, step in enumerate(steps):
            if self.state.cancelled:  # the user pressed stop
                self._say("(You were asked to stop. Say in a few words that you stopped.)", work)
                return
            tool = self.tools[step.tool]
            if missing := [r for r in tool.required if r not in step.args]:
                work.results.append((step.tool, step.args, Result(False, f"missing arguments: {', '.join(missing)}")))
                continue
            verdict = policy.decide(tool, step.args, self.state.last_text)
            if verdict.action == "handoff":
                self._hand_off(work.request, work, "root")
                return
            if verdict.action == "refuse":
                result = Result(False, verdict.text, final=True)
            elif verdict.action == "confirm":
                ok, question = self._preview(tool, step.args)
                if ok:
                    self.state.question = Question(tool, step.args, steps[i + 1:], work, f"May I {question}?")
                    self.on_question(self.state.question.text)
                    return
                result = Result(False, question, final=True)  # nothing matches: tell her, do not ask
            else:
                result = self.run_tool(tool, step.args)
            work.results.append((step.tool, step.args, result))
        self._after_steps(work)

    def _answered(self, question, yes):
        work = question.work
        if yes:
            result = self.run_tool(question.tool, question.args)
        else:
            result = Result(False, f"{self.config.user} said no, so it was not done.", final=True)
        work.results.append((question.tool.name, question.args, result))
        self._run_steps(question.rest, work)

    def _after_steps(self, work):
        """Speak the results. One real failure: plan once more. Two: hand the task to Claude Code."""
        failed = len(work.failures())
        if failed >= 2:
            log.info("two failures: hand-off")
            self._hand_off(work.request, work, "failures")
        elif failed == 1 and work.rounds == 1:
            work.rounds = 2
            self._carry_out(self._plan(work), work)
        else:
            self._say(self._results_note(work), work)

    READINGS = {
        "router": "it is about files, installing, a config, debugging, or deleting, so Claude Code does it.",
        "plan": "the companion's own tools cannot do it.",
        "root": "it needs root rights.",
        "failures": "the companion's tools failed two times.",
    }

    def _hand_off(self, task, work, reason="plan"):
        """Path A (an answer, no window) in its own thread, or Path B (a visible window) for a change."""
        path = handoff.choose_path(work.request, reason)
        folder = handoff.pick_folder(work.request, self.config)
        tried = [f"- {n}({a}) -> {'ok' if r.ok else 'FAILED'}: {r.text[:300]}" for n, a, r in work.results]
        health = ""
        if handoff.ABOUT_SYSTEM.search(work.request):  # the last health warnings, for a task about the system
            report = self.runner.run([str(self.config.bin("health"))], timeout=60).text
            health = "\n".join(line for line in report.splitlines() if line.startswith("WARN"))
        text = handoff.brief(self.config, work.request, f"Task: {task}. Handed over because {self.READINGS.get(reason, reason)}",
                             tried, work.snap.active if work.snap else "", folder, health)
        log.info("hand-off: path %s, folder %s, reason %s", path, folder, reason)
        if path == "B":
            result = handoff.hand_off_visible(self.runner, text, folder)
            work.results.append(("handoff", {"task": task}, result))
            self._say(f"(You handed this task to Claude Code in a window: {task}\nResult: {result.text}\n"
                      f"Tell {self.config.user} in one or two short lines. If it worked, say that Claude Code "
                      f"will ask {self.config.user} before each step in its window.)", work)
            return
        self.on_reply("thinking", "I am asking Claude Code. This can take a minute.")

        def job():
            self.queue.put(HandoffDone(work, task, handoff.ask(self.runner, text, folder)))
        threading.Thread(target=job, daemon=True).start()

    def _results_note(self, work):
        lines = []
        for name, args, r in work.results:
            text = r.text[:1500]
            if r.untrusted:
                text = f"{context.LABEL}\n{text}"
            lines.append(f"- {name}: {'done' if r.ok else 'NOT done'}: {text}")
        return (f"(What really happened for this request:\n" + "\n".join(lines) +
                f"\nTell {self.config.user} in one to three short sentences what was done and what was not, "
                f"or answer from these results. Claim only what this list shows.)")

    # ----- helpers -----

    def run_tool(self, tool, args):
        """Do one action. Exceptions become failed Results. Remembers what "it" means."""
        try:
            result = tool.run(**args)
        except TypeError as e:
            result = Result(False, f"wrong arguments for {tool.name}: {e}")
        except Exception as e:
            result = Result(False, f"{tool.name} failed: {e}")
        if result.ok and tool.name == "run_in_terminal" and policy.is_claude_command(str(args.get("command", ""))):
            self.state.last_target = ("claude", "")
        elif result.ok and tool.name in TARGET_ARGS:
            kind, arg = TARGET_ARGS[tool.name]
            self.state.last_target = (kind, str(args.get(arg, "")))
        self.mood.note_result(result.text)
        log.info("tool %s(%s) -> %s %r", tool.name, args, "ok" if result.ok else "FAILED", result.text[:300])
        return result

    @staticmethod
    def _preview(tool, args):
        """The yes/no question text, or (False, reason) when nothing matches."""
        if not tool.preview:
            return True, f'{tool.name.replace("_", " ")}: {", ".join(str(v) for v in args.values())}'
        try:
            return tool.preview(**args)
        except Exception:
            return False, f"wrong arguments for {tool.name}"

    def _say(self, note, work=None, keep=True):
        expression, text = voice.speak(self.config, self.mood, self.store.memory(), self.state.history, note,
                                       options=self.options)
        if work and work.results and any(not r.ok for _, _, r in work.results) and expression == "happy":
            expression = "idle"  # no happy face over a failure
        if keep:
            done = [f"{n}: {'ok' if r.ok else 'failed'}" for n, _, r in (work.results if work else [])]
            self.state.history.append({"role": "assistant", "content": f"[{expression}] {text}" +
                                       (f"  (tools: {'; '.join(done[-4:])})" if done else "")})
            del self.state.history[:-HISTORY_LIMIT]
        self.mood.save(self.state.history)
        log.info("reply [%s] %r", expression, text[:200])
        self.on_reply(expression, text)
