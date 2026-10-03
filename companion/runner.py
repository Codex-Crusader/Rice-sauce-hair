"""The result type of every tool, and the one runner for outside commands.

Tools get a Runner as a parameter, so a test can give them a fake runner instead.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Result:
    ok: bool
    text: str
    untrusted: bool = False  # the text holds words that someone else wrote (titles, file names)
    final: bool = False      # a clear answer (not found, refused, said no): no retry and no hand-off

    def __str__(self):
        return self.text


class Runner:
    def run(self, cmd, timeout=10, input=None, cwd=None):
        """Run a command and wait. ok is True when the exit code is 0. text is stdout, or stderr."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input, cwd=cwd)
        except (OSError, subprocess.TimeoutExpired) as e:
            return Result(False, f"error: {e}")
        return Result(r.returncode == 0, (r.stdout or r.stderr).strip())

    def spawn(self, cmd):
        """Start a program on its own (an app, a terminal) and do not wait for it.
        Under systemd, the app gets its own scope: a restart of the companion service must not stop it."""
        if os.environ.get("INVOCATION_ID") and shutil.which("systemd-run"):
            cmd = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "--", *cmd]
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return Result(False, f"error: {e}")
        return Result(True, "started")
