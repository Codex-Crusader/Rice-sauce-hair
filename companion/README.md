# Companion, the desktop companion

Companion lives in the bottom-right corner of the desktop. She talks, does desktop tasks from plain
or vague words, and hands hard tasks to Claude Code. Her model runs on this computer (Ollama, `qwen3:8b`).

- **Super+A**: talk to her. **Super+Shift+A**: hide or show her.
- **Right-click her face**: stop what she is doing, health check, pause her remarks, hide, restart, log, off.
- **Off switch**: `companion-switch off` (she stays off after a new login), `companion-switch on`.
- **Log**: `~/.cache/companion/brain.log`.

## How one request flows

```
ui -> session -> context.snapshot()                   what is on the screen (untrusted data)
              -> planner.route() or planner.plan()    a Decision: chat, ask, handoff, or do (1 to 5 steps)
              -> policy.decide() for each step        a Verdict: run, confirm, refuse, or handoff
              -> tools/ or handoff                    a Result (ok, text, untrusted, final)
              -> voice.speak()                        her reply, from the real results
              -> store                                chat, memory, mood, learned words
```

1. **Router (code, no model)**: some requests need no model. Files, installing, configs, debugging, and
   deleting always go to Claude Code. "Remember ...", "forget ...", "louder", "quieter", "system diagnostics",
   and an exact "open <app>" run at once.
2. **Plan call**: temperature 0, no persona, JSON output. It gets the screen, the chat, the tool list,
   and up to 5 **candidates**: the best matches for the words of the request in apps, windows, tabs,
   and files. "My code thing" finds PyCharm through the app categories. A step can pick a candidate
   by its number, so the model cannot name a thing that is not there.
3. **Policy**: the tier and the arguments decide, not the model (see Safety).
4. **Failures**: one failure makes one more plan call (done steps never run again). Two failures hand
   the task to Claude Code. "Not found" is an answer, not a failure.
5. **Speak call**: her persona, temperature 0.75, no tools. It gets the real results, so she says only
   what happened.

**Learned words**: when she guesses wrong and you say "no, I meant PyCharm", she stores the pair in
`~/.local/share/companion/aliases.json` ("music thing" -> PyCharm) and does the request again.
Learned words count before the built-in aliases.

## Safety

| Tier | Examples | What happens |
|---|---|---|
| Read | status, find files, list tabs | Runs at once |
| Small | open, focus, volume, brightness | Runs at once; she says what she did |
| Confirm | close a window or tabs, forget | She asks yes or no first |

- **Terminal commands** use an allowlist (`SAFE` in `policy.py`). One plain read-only program runs at
  once. Every other command asks first: pipes, redirects, `sh -c`, unknown programs. A command that
  destroys data is refused. A command with sudo goes to Claude Code.
- **Untrusted text**: window titles, tab titles, file names, and Claude Code's answers go to the model
  as labeled data, never as instructions.
- `remember` and `tell_claude` ask first unless your own message asked for them.
- A message typed into Claude Code is plain text only: it cannot start with `!`, `/`, `#`, or `-`.
- **Files**: the file tools (`open_file`, `show_in_file_manager`, `virus_scan`) check each path in code
  (`safe_path` in `policy.py`). The path must be in the home folder after symlinks are followed, and not
  in a deny folder. `open_file` also refuses scripts, `.desktop` files, and executable files, because
  opening them would run a program.
- **Virus scan**: `virus_scan` moves each file that ClamAV finds to `~/.local/share/companion/quarantine`,
  read only, with a record of where it was. It never deletes. It does not move links, or files in a deny
  folder or outside the home folder. `restore_from_quarantine` and `empty_quarantine` ask first.
  Each scan result is in `~/.local/share/companion/virus-scans.log`. `health` warns while the quarantine has files.

## Hand-off to Claude Code

Code selects the path:

- **Path A, questions and read-only work** ("why is my build failing", "what does this error mean"):
  `claude -p` runs with no window, in plan mode, with only Read, Grep, and Glob, and `--restricted`
  keeps its file tools inside the working folder. She says "I am asking Claude Code", and then reads
  the answer to you. It was tested: it did not edit, create, or run anything, and it could not read a
  file outside its folder.
- **Path B, changes** (install, edit, delete, fix, root, or two failures): a visible Kitty window.
  Claude Code asks you before each step there.

**The brief** has, in this order: your exact words, her reading of the request, what she tried with
the real output, the active window, the related folder, and the last health warnings for a system task.
The brief goes in on stdin (Path A) or after `--` (Path B), so it can never become a flag.

**The working folder** comes from the task: a path that you name, the repo for desktop and config
questions, or an empty folder of her own. It is never the home folder.

### Privacy

Her own model is local. **Path A and Path B send the brief to Anthropic** through your Claude account,
so she is not fully local while she hands a task off. Paths on the deny list never go into a brief and
are never the working folder. The file tools refuse them too:

```toml
# persona.toml
[handoff]
deny = ["~/.ssh", "~/.gnupg", ...]
```

## Files

| File | Job |
|---|---|
| `main.py` | GTK application, signals, timers (greeting, idle remarks, battery) |
| `ui.py` | The window: her face, the bubble, Yes and No. It holds no conversation state. |
| `session.py` | One worker thread, the queue, all state, and the flow of a request |
| `planner.py` | The router and the plan call (Decision) |
| `candidates.py` | The best matches for vague words |
| `policy.py` | The one safety decision (Verdict), the command allowlist, the file boundary |
| `voice.py` | The speak call and the cleanup of her reply |
| `handoff.py` | Path A, Path B, the brief, the working folder, the deny list |
| `context.py` | The screen snapshot |
| `tools/` | The actions, by area: windows, apps, browser, system, files, memory |
| `runner.py` | Result, and the one runner for outside commands |
| `llm.py` | Only the HTTP calls to Ollama |
| `config.py`, `store.py` | The persona and paths; all files on disk (atomic writes) |
| `mood.py` | Her mood and her sense of time |
| `chrome_bridge.py`, `chrome-extension/` | Tab control (run `setup.sh` once) |
| `persona.toml` | Her character, the model, the expressions, the deny list |

## Tests

```sh
cd ~/dotfiles/companion
python3 -m unittest discover -s tests -p 'test_*.py'   # no model needed, under 1 second
python3 tests/eval.py                                  # the real model, about 3 minutes; exits 1 on a failure
python3 tests/eval.py close                            # only the cases whose name contains "close"
```

The unit tests use a fixed set of programs, aliases, and apps (`setUpModule` in `test_safety.py`).
They do not depend on what is installed on the machine.

The eval records actions and does not do them, and it uses a temporary data folder. It replaces the
two hand-off paths with recorders, so it does not call Claude Code.
