"""Find and open files in the home folder."""
import os
import re
import time
from pathlib import Path

from runner import Result
from tools.common import spawn


# ---------- files ----------

HOME = Path.home()
KINDS = {
    "document": ["pdf", "doc", "docx", "odt", "txt", "md", "rtf", "xlsx", "ods", "csv", "pptx", "odp"],
    "image": ["png", "jpg", "jpeg", "webp", "gif", "svg", "bmp", "heic"],
    "video": ["mp4", "mkv", "webm", "mov", "avi"],
    "audio": ["mp3", "flac", "ogg", "wav", "m4a", "opus"],
    "code": ["py", "lua", "sh", "js", "ts", "c", "cpp", "h", "rs", "go", "java", "json", "toml", "yaml", "yml"],
    "archive": ["zip", "tar", "gz", "xz", "zst", "7z", "rar"],
}


def find_files(runner, words, kind="any"):
    """Search the home folder by name with fd. Newest first, at most 20."""
    # --full-path: the words may be in a folder name too ("wallpaper" finds ~/Pictures/wallpaper/x.jpg)
    cmd = ["fd", "--ignore-case", "--absolute-path", "--full-path", "--exclude", ".cache", "--exclude", ".local/share/Trash",
           "--max-results", "200"]
    if kind == "folder":
        cmd += ["--type", "d"]
    else:
        cmd += ["--type", "f"] + [arg for ext in KINDS.get(kind, []) for arg in ("--extension", ext)]
    pattern = ".*".join(re.escape(w) for w in str(words).split()) or "."
    out = runner.run(cmd + [pattern, str(HOME)], timeout=20).text
    paths = [Path(p) for p in out.splitlines() if p.startswith("/") and "/.local/share/Trash" not in p]
    if kind == "folder":  # shallow folders first: "pictures" means ~/Pictures, not a folder deep inside
        paths.sort(key=lambda p: len(p.parts))
        rows = "\n".join(str(p).replace(str(HOME), "~", 1) for p in paths[:20])
        return Result(True, rows, untrusted=True) if rows else Result(False, f'no folder matches "{words}"', final=True)
    if not paths:
        return Result(False, f'no {kind if kind != "any" else ""} files match "{words}" in the home folder', final=True)
    paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    rows = []
    for p in paths[:20]:
        when = time_ago(p.stat().st_mtime) if p.exists() else "?"
        rows.append(f"{str(p).replace(str(HOME), '~', 1)}  ({when})")
    more = f"\n... and {len(paths) - 20} more" if len(paths) > 20 else ""
    return Result(True, "\n".join(rows) + more, untrusted=True)


def fix_home(path):
    """Map an invented home folder (/home/someone/...) to the real one."""
    path = os.path.expanduser(str(path).strip())
    return re.sub(r"^/home/[^/]+", str(HOME), path) if path.startswith("/home/") else path


def resolve(path):
    p = Path(fix_home(path))
    return p if p.exists() else None


def open_file(runner, path):
    p = resolve(path)
    if not p:
        return Result(False, f"{path} does not exist", final=True)
    return spawn(runner, ["xdg-open", str(p)], f"opened {p.name}")


def show_in_file_manager(runner, path):
    p = resolve(path)
    if not p:
        return Result(False, f"{path} does not exist", final=True)
    folder = p if p.is_dir() else p.parent
    return spawn(runner, ["pcmanfm-qt", str(folder)], f"opened the folder {folder}")


def time_ago(timestamp):
    seconds = max(0, time.time() - timestamp)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"
