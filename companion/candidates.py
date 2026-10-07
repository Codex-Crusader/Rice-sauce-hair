"""Candidates: the 5 best matches for the words of a request, in apps, windows, tabs, and files.

The plan call picks a candidate by its number, so it cannot name a thing that is not there.
Vague words find things through app categories: "my code thing" -> Development/IDE -> PyCharm.
Files are searched only when the request is about a file ("that pdf from yesterday").
Words that the user taught her (the store's aliases) count first.
"""
import re
import time
from dataclasses import dataclass
from pathlib import Path

from planner import Step
from tools.apps import app_categories, desktop_entries, find_app
from tools.files import KINDS, SCAN_LIMIT, newest, short

LIMIT = 5
# "open kitty" means a new one; "bring up kitty" means the open window
OPEN_NEW = re.compile(r"\b(open|start|launch|run|fire up|boot up|kholo|khol do|chalao|chala do)\b", re.IGNORECASE)
BRING_UP = re.compile(r"\b(bring up|show me|switch to|go to|back to|focus|pull up)\b", re.IGNORECASE)
STOP = {"the", "a", "an", "my", "me", "i", "it", "that", "this", "thing", "stuff", "one", "up", "please", "pls",
        "can", "could", "you", "open", "bring", "show", "start", "launch", "switch", "go", "to", "back", "focus",
        "run", "find", "get", "put", "on", "from", "for", "of", "and", "with", "app", "window", "tab", "some",
        "want", "need", "let", "see", "where", "is", "was", "again", "now", "just"}
# Vague words -> the app categories of the .desktop files
CATEGORY_WORDS = {
    "code": {"Development", "IDE"}, "coding": {"Development", "IDE"}, "ide": {"IDE"}, "editor": {"TextEditor", "IDE"},
    "programming": {"Development", "IDE"}, "browser": {"WebBrowser"}, "web": {"WebBrowser"},
    "internet": {"WebBrowser"}, "music": {"Audio", "Music"}, "song": {"Audio", "Music"}, "video": {"Video"},
    "movie": {"Video"}, "terminal": {"TerminalEmulator"}, "shell": {"TerminalEmulator"},
    "console": {"TerminalEmulator"}, "files": {"FileManager"}, "folder": {"FileManager"}, "chat": {"InstantMessaging"},
    "mail": {"Email"}, "email": {"Email"}, "game": {"Game"}, "games": {"Game"}, "office": {"Office"},
    "photo": {"Photography", "Graphics"}, "image": {"Graphics"}, "draw": {"2DGraphics", "RasterGraphics"},
    "settings": {"Settings"}, "monitor": {"Monitor"}, "tasks": {"Monitor"},
}
FILE_WORDS = re.compile(r"\b(pdf|file|files|document|doc|docx|picture|pictures|photo|image|screenshot|video|"
                        r"song|download|downloaded|spreadsheet|slides|presentation)\b", re.IGNORECASE)
FILE_KINDS = [(r"\bpdf\b", ["pdf"]), (r"\b(picture|photo|image|screenshot)s?\b", KINDS["image"]),
              (r"\bvideos?\b", KINDS["video"]), (r"\bsongs?\b", KINDS["audio"]),
              (r"\b(document|doc|docx)s?\b", KINDS["document"]),
              (r"\b(spreadsheet)s?\b", ["xlsx", "ods", "csv"]), (r"\b(slides|presentation)\b", ["pptx", "odp"])]
FILE_TIMES = [(r"\btoday\b", "1d"), (r"\byesterday\b", "2d"), (r"\b(this|last) week\b", "8d"),
              (r"\b(recent|recently|latest|new|newest|last)\b", "3d")]


@dataclass
class Candidate:
    label: str      # what the plan call sees, e.g. "window: jetbrains-pycharm | robot_arm - main.py"
    step: Step      # what runs when the plan call picks it
    score: float


def words_of(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9+.-]*", text.lower()) if w not in STOP and len(w) > 1]


def overlap(words, text):
    """How many request words are in text (a whole word, or the start of one)."""
    have = set(re.findall(r"[a-z0-9]+", text.lower()))
    return sum(1 for w in words if w in have or (len(w) >= 4 and any(h.startswith(w) for h in have)))


def find(request, snap, runner, learned=None, home=None):
    """The best candidates for the request, highest score first. snap: context.Snapshot (or None)."""
    home = home or Path.home()  # at call time, not at import (a test can change the home folder)
    words = words_of(request)
    if not words:
        return []
    learned = learned or {}
    taught = [v for k, v in learned.items() if k and set(k.split()) <= set(words)]  # e.g. "code thing" -> PyCharm
    cats = set().union(*(CATEGORY_WORDS.get(w, set()) for w in words))
    categories = app_categories()
    open_new = bool(OPEN_NEW.search(request) and not BRING_UP.search(request))  # then windows rank after apps
    found = []

    def app_score(app_id, name):
        s = 2 * overlap(words, f"{name} {app_id.replace('.', ' ').replace('-', ' ')}")
        s += 1.5 * len(cats & set(categories.get(app_id, [])))
        s += 5 * sum(1 for t in taught if t.lower() in (name.lower(), app_id.lower()))
        return s

    for app_id, name, _ in desktop_entries():
        if (s := app_score(app_id, name)) > 0:
            found.append(Candidate(f"app: {name}", Step("open_app", {"name": name}), s))
    for line in (snap.windows.splitlines() if snap else []):
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) < 2:
            continue
        cls, title = parts[0], parts[1]
        app = find_app(cls, learned=learned)
        match = 2 * overlap(words, f"{cls} {title}") + (app_score(*app[1][:2]) if app else 0)
        if match > 0:
            s = match / 2 - 0.1 if open_new else match + 0.5
            found.append(Candidate(f"window: {cls} | {title}", Step("focus_window", {"window": cls}), s))
    for line in (snap.tabs.splitlines() if snap else []):
        title, _, url = line.lstrip("* ").partition(" | ")
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        hit = next((w for w in words if overlap([w], f"{title} {host}")), None)
        if hit:
            found.append(Candidate(f"tab: {title[:60]} | {host}", Step("switch_tab", {"tab": hit}),
                                   2 * overlap(words, f"{title} {host}") + 0.5))
    if FILE_WORDS.search(request):
        found += files(request, words, runner, home)
    found.sort(key=lambda c: c.score, reverse=True)
    return found[:LIMIT]


def files(request, words, runner, home):
    """Recent files that fit the request: fd, by kind and age, newest first."""
    exts = next((e for pattern, e in FILE_KINDS if re.search(pattern, request, re.IGNORECASE)), [])
    age = next((a for pattern, a in FILE_TIMES if re.search(pattern, request, re.IGNORECASE)), "")
    names = [w for w in words if not FILE_WORDS.search(w) and not any(re.search(p, w) for p, _ in FILE_TIMES)]
    cmd = ["fd", "--type", "f", "--ignore-case", "--absolute-path", "--exclude", ".cache", "--exclude", ".local/share",
           "--max-results", str(SCAN_LIMIT), *[a for e in exts for a in ("--extension", e)]]
    if age:
        cmd += ["--changed-within", age]
    cmd += [".*".join(re.escape(w) for w in names) or ".", str(home)]
    paths = [Path(p) for p in runner.run(cmd, timeout=10).text.splitlines() if p.startswith("/")]
    out = []
    for i, (changed, p) in enumerate(newest(paths, LIMIT)):
        when = time.strftime("%d %b %H:%M", time.localtime(changed)) if changed else "?"
        out.append(Candidate(f"file: {short(p, home)} (changed {when})", Step("open_file", {"path": str(p)}), 3 - 0.3 * i))
    return out
