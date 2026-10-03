"""What all tools share: the Tool record, and helpers that turn a command into a Result."""
from dataclasses import dataclass
import json
from typing import Callable

from runner import Result


@dataclass
class Tool:
    name: str
    tier: str
    description: str
    params: dict          # JSON schema "properties"
    required: list
    run: Callable
    preview: Callable = None  # returns (ok, question text) before the user is asked; not ok = nothing matches


def act(runner, cmd, done):
    """Run a command that changes something. ok follows the exit code."""
    r = runner.run(cmd)
    return Result(True, done) if r.ok else Result(False, f"failed: {r.text or 'exit code not 0'}")


def spawn(runner, cmd, done):
    """Start a program on its own (an app, a window)."""
    r = runner.spawn(cmd)
    return Result(True, done) if r.ok else Result(False, f"failed: {r.text}")


def hypr_json(runner, what):
    try:
        return json.loads(runner.run(["hyprctl", what, "-j"]).text)
    except json.JSONDecodeError:
        return []


def dispatch(runner, lua):
    r = runner.run(["hyprctl", "dispatch", lua])
    return Result(True, r.text or "ok") if r.ok else Result(False, f"failed: {r.text}")
