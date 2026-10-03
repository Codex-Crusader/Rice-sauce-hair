"""The one owner of the safety decision. A tool only does its action; this module decides
if it runs, asks first, is refused, or goes to Claude Code.

decide() is pure: it reads only the tool, the arguments, and the user's words.
The command gate for run_in_terminal is an allowlist: one plain read-only program runs at once,
every other command asks first, and commands that destroy data or need root are refused.
"""
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import REPO

TIER_READ, TIER_SMALL, TIER_CONFIRM = "0", "1", "1b"


@dataclass
class Verdict:
    action: str     # "run" | "confirm" | "refuse" | "handoff"
    text: str = ""  # the reason ("refuse": it goes back as the tool result; "handoff": for the log)


# ---------- the user's own words ----------

REMEMBER = r"^\s*(please\s+)?remember\b|\bdon'?t forget\b"
TALK_TO_CLAUDE = re.compile(r"\bclaude\b.*\b(tell|ask|send|say|type|write)\b|\b(tell|ask|send|say|type|write)\b.*\bclaude\b", re.I)
SEND_IT = re.compile(r"^\s*(now\s+)?(send|tell|say|type|ask)\b", re.I)
# Tools that run at once only when the user's own message asked for them; otherwise she asks first.
# A web page title could otherwise make her save a "fact" or type into Claude Code.
ASK_UNLESS_REQUESTED = {"remember", "tell_claude"}


def words_in(message, text):
    """True when most words of message are in text: The user said it, the model did not make it up."""
    words = re.findall(r"[a-z0-9']{2,}", message.lower())
    said = set(re.findall(r"[a-z0-9']{2,}", text.lower()))
    return not words or sum(w in said for w in words) >= 2 * len(words) / 3


def user_asked(name, args, user_text):
    if name == "remember":
        return bool(re.search(REMEMBER, user_text, re.I))
    if name == "tell_claude":
        return bool(TALK_TO_CLAUDE.search(user_text) or SEND_IT.search(user_text)) and \
            words_in(str(args.get("message", "")), user_text)
    return True


# ---------- the command gate ----------

SAFE = {"ls", "cat", "less", "head", "tail", "grep", "rg", "df", "du", "free", "uptime", "date", "cal",
        "whoami", "uname", "lsblk", "lspci", "lsusb", "ping", "htop", "btop", "top", "nvtop", "nvidia-smi",
        "sensors", "fastfetch", "wc", "which", "file", "stat", "echo", "pwd", "health", "journalctl"}
# Programs that are safe only with these first arguments
SAFE_SUBCOMMANDS = {"git": {"status", "log", "diff", "show", "branch"},
                    "systemctl": {"status", "--failed", "list-units", "list-timers", "--user"},
                    "pacman": {"-Q", "-Qi", "-Ql", "-Qe", "-Qs", "-Ss", "-Si", "-Qu"}}
SHELL_SYNTAX = re.compile(r"[;&|<>`$(){}\\\n]")
# Arguments that make a read-only program write files or run other programs (rg --pre, git log --output)
UNSAFE_ARGS = re.compile(r"^--?(vacuum|rotate|flush|setup-keys|relinquish|exec|delete|output|pre\b|pager|"
                         r"ext-diff|gen-config|config|compile)", re.I)
ROOT_PROGRAMS = {"sudo", "su", "doas", "pkexec", "run0"}
# Commands that would destroy the system or the home folder: never run, never even ask.
CATASTROPHIC = re.compile(
    r"\brm\s+(-\w*\s+)*(-\w*[rR]\w*\s+)(-\w*\s+)*(~/?|/|/home/?|/home/\w+/?|\$HOME/?|\*|\.\.?/?)(\s|$)"
    r"|\bmkfs|\bwipefs\b|\bdd\b.*\bof=/dev/|\bchmod\s+-R\s+\S+\s+/(\s|$)|:\(\)\s*\{\s*:\|:&\s*\};:")
TERMINAL_ONLY = ("", "kitty", "terminal", "zsh", "bash", "shell")  # an empty terminal, no command
SHELL_WORDS = {"cd", "echo", "source", ".", "export", "for", "while", "if", "time", "exec", "set", "["}


def command_words(command):
    """The program names of a command line: the first word, and each word after ; & | ( or a newline."""
    return [m.group(1) for m in re.finditer(r"(?:^|[;&|(\n])\s*(?:\w+=\S*\s+)*([^\s;&|()]+)", command)]


def needs_root(command):
    return any(Path(w).name in ROOT_PROGRAMS for w in command_words(command))


def is_claude_command(command):
    return bool(re.match(r"^\s*claude(\s|$)", command))


def command_is_safe(command):
    """True only for one plain read-only program from SAFE (or SAFE_SUBCOMMANDS),
    with an optional "cd <folder> && " in front."""
    command = re.sub(r"^\s*cd\s+[\w~./-]+\s*&&\s*", "", command)
    if SHELL_SYNTAX.search(command):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if not words or "/" in words[0] or any(UNSAFE_ARGS.match(w) for w in words[1:]):
        return False
    if words[0] == "git":  # options that only select the repository come before the subcommand
        while len(words) > 1 and (re.match(r"--(git-dir|work-tree)=", words[1]) or words[1] in ("--no-pager", "-C")):
            words = [words[0]] + words[3 if words[1] == "-C" else 2:]
    if words[0] in SAFE:
        return True
    allowed = SAFE_SUBCOMMANDS.get(words[0])
    return bool(allowed) and len(words) > 1 and words[1] in allowed


def shell_aliases():
    """Alias names from the zsh files, so "prime-run" counts as a program."""
    names = set()
    for f in [Path.home() / ".zshrc", *(REPO / "shell").glob("*.zsh")]:
        try:
            names.update(re.findall(r"^\s*alias\s+([\w-]+)=", f.read_text(), re.M))
        except OSError:
            pass
    return names


def program_exists(command):
    words = command_words(command)
    first = words[0] if words else ""
    return first in SHELL_WORDS or bool(shutil.which(os.path.expanduser(first))) or first in shell_aliases()


def command_verdict(command):
    """The verdict for run_in_terminal."""
    command = str(command)
    if command.strip().lower() in TERMINAL_ONLY or is_claude_command(command):
        return Verdict("run")  # an empty terminal, or Claude Code (it asks before each change itself)
    if CATASTROPHIC.search(command):
        return Verdict("refuse", "REFUSED: this command would destroy the home folder or the system. "
                                 "Do not run it, do not ask again, and tell the user plainly that you will not do this.")
    if needs_root(command):
        return Verdict("handoff", "this needs root rights, so Claude Code does it (it asks before each step)")
    if not program_exists(command):
        words = command_words(command)
        return Verdict("refuse", f'failed: there is no program named "{words[0] if words else command}". '
                                 f'Check what the user meant.')
    return Verdict("run") if command_is_safe(command) else Verdict("confirm")


# ---------- the decision ----------

def decide(tool, args, user_text=""):
    """Verdict for one tool call. tool has .name and .tier. user_text is the user's message."""
    if tool.name == "run_in_terminal":
        verdict = command_verdict(args.get("command", ""))
    elif tool.tier == TIER_CONFIRM:
        verdict = Verdict("confirm")
    else:
        verdict = Verdict("run")
    if verdict.action != "run":
        return verdict
    if tool.name in ASK_UNLESS_REQUESTED and not user_asked(tool.name, args, user_text):
        return Verdict("confirm")
    return verdict
