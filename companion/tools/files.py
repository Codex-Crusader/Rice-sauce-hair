"""Find and open files in the home folder."""
import heapq
import re
import time
from pathlib import Path

from policy import PathRefused, safe_path, safe_to_open
from runner import Result
from tools.common import spawn

# ---------- files ----------

SHOWN = 20          # rows in the answer
SCAN_LIMIT = 5000   # fd stops here; enough for a name search, bounded for "."
KINDS = {
    "document": ["pdf", "doc", "docx", "odt", "txt", "md", "rtf", "xlsx", "ods", "csv", "pptx", "odp"],
    "image": ["png", "jpg", "jpeg", "webp", "gif", "svg", "bmp", "heic"],
    "video": ["mp4", "mkv", "webm", "mov", "avi"],
    "audio": ["mp3", "flac", "ogg", "wav", "m4a", "opus"],
    "code": ["py", "lua", "sh", "js", "ts", "c", "cpp", "h", "rs", "go", "java", "json", "toml", "yaml", "yml"],
    "archive": ["zip", "tar", "gz", "xz", "zst", "7z", "rar"],
}


def find_files(runner, words, kind="any"):
    """Search the home folder by name with fd. Newest first, at most SHOWN.
    fd skips hidden folders (~/.ssh, ~/.gnupg) and git-ignored files by default."""
    home = Path.home()
    # --full-path: the words may be in a folder name too ("wallpaper" finds ~/Pictures/wallpaper/x.jpg)
    cmd = ["fd", "--ignore-case", "--absolute-path", "--full-path", "--max-results", str(SCAN_LIMIT)]
    if kind == "folder":
        cmd += ["--type", "d"]
    else:
        cmd += ["--type", "f"] + [arg for ext in KINDS.get(kind, []) for arg in ("--extension", ext)]
    pattern = ".*".join(re.escape(w) for w in str(words).split()) or "."
    out = runner.run(cmd + [pattern, str(home)], timeout=20).text
    paths = [Path(p) for p in out.splitlines() if p.startswith("/")]
    if not paths:
        what = "folder" if kind == "folder" else f"{kind} file" if kind != "any" else "file"
        return Result(False, f'no {what} matches "{words}" in the home folder', final=True)
    if kind == "folder":  # shallow folders first: "pictures" means ~/Pictures, not a folder deep inside
        best = heapq.nsmallest(SHOWN, paths, key=lambda p: len(p.parts))
        rows = [short(p, home) for p in best]
    else:
        rows = [f"{short(p, home)}  ({time_ago(t) if t else '?'})" for t, p in newest(paths, SHOWN)]
    more = f"\n... and {len(paths) - SHOWN} more" if len(paths) > SHOWN else ""
    return Result(True, "\n".join(rows) + more, untrusted=True)


def newest(paths, n):
    """The n newest paths as (mtime, path). One stat for each path; O(len(paths) * log n), not a full sort."""
    return heapq.nlargest(n, ((mtime(p), p) for p in paths), key=lambda pair: pair[0])


def mtime(path):
    try:
        return path.stat().st_mtime
    except OSError:  # deleted between fd and stat
        return 0


def short(path, home):
    return "~" + str(path)[len(str(home)):] if path.is_relative_to(home) else str(path)


def open_file(runner, deny, path):
    try:
        p = safe_to_open(path, deny)
    except PathRefused as e:
        return Result(False, f"refused: {e}. Tell the user plainly.", final=True)
    return spawn(runner, ["xdg-open", str(p)], f"opened {p.name}")


def show_in_file_manager(runner, deny, path):
    try:
        p = safe_path(path, deny)
    except PathRefused as e:
        return Result(False, f"refused: {e}. Tell the user plainly.", final=True)
    folder = p if p.is_dir() else p.parent
    return spawn(runner, ["pcmanfm-qt", str(folder)], f"opened the folder {folder}")


def time_ago(timestamp):
    seconds = max(0, time.time() - timestamp)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"
