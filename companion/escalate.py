"""Claude Code windows that Castorice opens, and can type into later.

Each window gets a private Kitty control socket (socket-only remote control), so she can
send text to the windows she opened, and to no other window.
Claude Code asks the user before each change, so nothing runs without approval.
"""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

CLAUDE = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
SOCKETS = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))

PREFIX = ("Castorice (the desktop companion) handed over this task from the user. "
          "Ask the user before each change. Task: ")


def open_claude(prompt=""):
    """A new Kitty window with Claude Code, and the prompt as the first message (if any)."""
    socket = SOCKETS / f"castorice-claude-{int(time.time() * 1000)}"
    subprocess.Popen(
        # ~/dotfiles is a trusted folder, so Claude Code does not stop at "Do you trust this folder?"
        ["kitty", "--title", "Claude Code (from Castorice)", "--directory", str(Path.home() / "dotfiles"),
         "-o", "allow_remote_control=socket-only", "--listen-on", f"unix:{socket}",
         CLAUDE] + ([prompt] if prompt else []),
        start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Claude Code is open in a new window" + (" with the message." if prompt else ".")


def ask_claude(task, context=""):
    """A big or risky task: a new Claude Code window with the full task and the recent chat."""
    open_claude(PREFIX + task + (f"\n\nRecent chat with Castorice, for context:\n{context}" if context else ""))
    return "Claude Code is open in a new window with the task."


def _kitty(socket, *args, text=None):
    return subprocess.run(["kitty", "@", "--to", f"unix:{socket}", *args], input=text, text=True,
                          capture_output=True, timeout=5)


def _wait_ready(socket, seconds=20):
    """Wait until Claude Code shows its prompt. Returns "ready", "question", or "gone"."""
    for _ in range(seconds * 2):
        screen = _kitty(socket, "get-text")
        if screen.returncode != 0:
            return "gone"
        if re.search(r"trust (this|the) folder|Do you trust", screen.stdout, re.I):
            return "question"
        if "\u276f" in screen.stdout:  # the prompt sign: Claude Code is ready for input
            return "ready"
        time.sleep(0.5)
    return "question"  # not ready in time: do not type blindly


def tell_claude(message):
    """Type a message into the newest open Claude Code window, then press Enter.
    With no open window, open one with the message."""
    for socket in sorted(SOCKETS.glob("castorice-claude-*"), reverse=True):
        state = _wait_ready(socket)
        if state == "gone":
            continue
        if state == "question":
            return ("NOT SENT: Claude Code is waiting for an answer on its screen (for example a trust question). "
                    "Tell the user to answer it in the Claude window, then ask again.")
        _kitty(socket, "send-text", "--stdin", text=message.strip())
        time.sleep(0.4)  # Enter apart from the text, so it is not read as part of a paste
        _kitty(socket, "send-text", "--stdin", text="\r")
        return f'typed "{message}" into the open Claude Code window and pressed Enter'
    return open_claude(message)
