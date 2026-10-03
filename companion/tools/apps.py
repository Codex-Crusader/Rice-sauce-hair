"""Find and open installed apps (.desktop files)."""
import re
from pathlib import Path

from runner import Result
from tools.common import spawn


# ---------- apps and links ----------

APP_DIRS = [Path.home() / ".local/share/applications", Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications"]
_cache = {"key": None, "entries": []}


def _entries():
    """(id, name, terminal command or None, categories) of visible apps, read again only when a folder changes.
    Hidden entries (NoDisplay=true) are skipped. Terminal apps (Terminal=true, e.g. the ros2 distrobox)
    get their command, to run in Kitty."""
    key = tuple(d.stat().st_mtime if d.is_dir() else 0 for d in APP_DIRS)
    if key != _cache["key"]:
        entries = []
        for d in APP_DIRS:
            for f in d.glob("*.desktop"):
                lines = f.read_text(errors="ignore").split("[Desktop Action")[0].splitlines()
                if "NoDisplay=true" in lines:
                    continue
                name = next((l[5:].strip() for l in lines if l.startswith("Name=")), f.stem)
                command = None
                if "Terminal=true" in lines:
                    exec_line = next((l[5:] for l in lines if l.startswith("Exec=")), "")
                    command = re.sub(r"\s%[a-zA-Z]", "", exec_line).strip() or None
                categories = next((l[11:].strip(";").split(";") for l in lines if l.startswith("Categories=")), [])
                entries.append((f.stem, name, command, categories))
        _cache.update(key=key, entries=entries)
    return _cache["entries"]


def desktop_entries():
    """(id, name, terminal command or None) of visible apps."""
    return [e[:3] for e in _entries()]


def app_categories():
    """{app id: [categories]}, e.g. pycharm: [Development, IDE, Java]."""
    return {e[0]: e[3] for e in _entries()}


def app_names():
    """Names of the installed apps, for her hints."""
    return ", ".join(sorted({name for _, name, _ in desktop_entries()}))


# Short names that people use for apps here. A value with "/" is a script in the repo, not an app name.
APP_ALIASES = {"settings": "bin/settings-menu", "system settings": "bin/settings-menu", "ros": "Ros2", "ros 2": "Ros2",
               "terminal": "kitty", "files": "PCManFM-Qt File Manager", "file manager": "PCManFM-Qt File Manager",
               "browser": "Google Chrome", "chrome": "Google Chrome", "task manager": "Mission Center",
               "sound": "Volume Control", "volume": "Volume Control", "bluetooth": "Bluetooth Manager",
               "pycharm": "PyCharm Community Edition", "wifi": "Advanced Network Configuration"}


def find_app(name, fuzzy=True, learned=None):
    """(score, (id, name, terminal command)) of the best app for a name, or None.
    learned: words the user taught her ("code thing" -> "PyCharm"); checked before APP_ALIASES.
    Score 0: exact name, id, or alias. 1: name starts with it. 2: name contains it. 3 to 5: a part of the name."""
    name = " ".join(name.split())
    q = ((learned or {}).get(name.lower()) or APP_ALIASES.get(name.lower(), name)).lower()
    best = None
    for entry in desktop_entries():
        app_id, app_name = entry[0].lower(), entry[1].lower()
        if q in (app_name, app_id) or app_id.endswith("." + q):
            score = 0
        elif app_name.startswith(q):
            score = 1
        elif q in app_name or q in app_id:
            score = 2
        else:
            continue
        if best is None or (score, len(entry[1])) < (best[0], len(best[1][1])):
            best = (score, entry)
    if best is None and fuzzy:  # "jetbrains-pycharm" (a window class): try "pycharm", then "jetbrains"
        for part in sorted(set(re.split(r"[^\w]+", q)) - {q}, key=len, reverse=True):
            if len(part) >= 4 and (found := find_app(part, fuzzy=False, learned=learned)):
                return (found[0] + 3, found[1])
    return best


def open_app(runner, repo, store, name):
    """Open the best match: exact name, id, or alias first, then names that start with it, then contains."""
    alias = APP_ALIASES.get(name.lower().strip(), "")
    if "/" in alias:  # a script in the repo, e.g. the settings menu
        return spawn(runner, [str(repo / alias)], f"opened {name}")
    found = find_app(name, learned=store.aliases())
    if not found:
        return Result(False, f'no app matches "{name}": {name} is not installed. '
                             f'Tell the user plainly that it is not installed.', final=True)
    app_id, app_name, command = found[1]
    launch = ["kitty", "--title", app_name, "sh", "-c", command] if command else ["gtk-launch", app_id]
    return spawn(runner, launch, f"opened {app_name}")
