"""Tools that Castorice can use.

Each tool has a tier. The tier, not the model, decides what happens:
  0  read only            runs at once
  1  small, reversible    runs at once, she says what she did
  1b closes something     she asks "yes or no?" first
  2  anything bigger      not a tool: she hands it to Claude Code (escalate.py)
"""
import json
import os
import re

import escalate
import urllib.parse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

TIER_READ, TIER_SMALL, TIER_CONFIRM = "0", "1", "1b"
MEMORY_FILE = Path.home() / ".local/share/castorice/memory.json"


@dataclass
class Tool:
    name: str
    tier: str
    description: str
    params: dict          # JSON schema "properties"
    required: list
    run: Callable
    preview: Callable = None  # confirm tools: returns (ok, question text) before the user is asked
    needs_confirm: Callable = None  # small tools: True for risky arguments, then the user is asked first


def sh(*cmd, timeout=10):
    """Run a command and return its output (stdout, or the error text)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"error: {e}"


def hypr_json(what):
    try:
        return json.loads(sh("hyprctl", what, "-j"))
    except json.JSONDecodeError:
        return []


def dispatch(lua):
    return sh("hyprctl", "dispatch", lua)


# ---------- windows ----------

def list_windows():
    rows = [f'{w["class"]} | {w["title"][:60]} | workspace {w["workspace"]["name"]}'
            for w in hypr_json("clients") if w.get("mapped") and w["class"] != "castorice"]
    return "\n".join(rows) or "no windows"


def find_window(query):
    """Return the address of the first window whose class or title contains query."""
    q = query.lower()
    for w in hypr_json("clients"):
        if q in w["class"].lower() or q in w["title"].lower():
            return w["address"]
    return None


def window_action(lua_template):
    def run(window):
        addr = find_window(window)
        if not addr:
            return f'no window matches "{window}"'
        return dispatch(lua_template.format(sel=f"address:{addr}"))
    return run


def describe_window(window):
    for w in hypr_json("clients"):
        if window.lower() in w["class"].lower() or window.lower() in w["title"].lower():
            return True, f'close the window "{w["title"][:50]}" ({w["class"]})'
    return False, f'no window matches "{window}". Call list_windows first.'


def move_window(window, workspace):
    addr = find_window(window)
    if not addr:
        return f'no window matches "{window}"'
    return dispatch(f'hl.dsp.window.move({{ window = "address:{addr}", workspace = {int(workspace)} }})')


# ---------- apps and links ----------

def desktop_entries():
    """(id, name, terminal command or None) of visible apps. Hidden entries (NoDisplay=true) are skipped.
    Terminal apps (Terminal=true, e.g. a distrobox) get their command, to run in Kitty."""
    dirs = [Path.home() / ".local/share/applications", Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications")]
    for d in dirs:
        for f in d.glob("*.desktop"):
            lines = f.read_text(errors="ignore").split("[Desktop Action")[0].splitlines()
            if "NoDisplay=true" in lines:
                continue
            name = next((l[5:].strip() for l in lines if l.startswith("Name=")), f.stem)
            command = None
            if "Terminal=true" in lines:
                exec_line = next((l[5:] for l in lines if l.startswith("Exec=")), "")
                command = re.sub(r"\s%[a-zA-Z]", "", exec_line).strip() or None
            yield f.stem, name, command


def app_names():
    """Names of the installed apps, for her hints."""
    return ", ".join(sorted({name for _, name, _ in desktop_entries()}))


# Short names that people use for apps here. A value with "/" is a command, not an app name.
APP_ALIASES = {"settings": str(Path.home() / "dotfiles/bin/settings-menu"), "system settings":
               str(Path.home() / "dotfiles/bin/settings-menu"), "terminal": "kitty", "files": "PCManFM-Qt File Manager", "file manager": "PCManFM-Qt File Manager",
               "browser": "Google Chrome", "chrome": "Google Chrome", "task manager": "Mission Center",
               "sound": "Volume Control", "volume": "Volume Control", "bluetooth": "Bluetooth Manager",
               "pycharm": "PyCharm Community Edition", "wifi": "Advanced Network Configuration"}


def find_app(name):
    """(score, (id, name, terminal command)) of the best app for a name, or None.
    Score 0: exact name, id, or alias. 1: name starts with it. 2: name contains it."""
    name = " ".join(name.split())
    q = APP_ALIASES.get(name.lower(), name).lower()
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
    return best


def open_app(name):
    """Open the best match: exact name, id, or alias first, then names that start with it, then contains."""
    alias = APP_ALIASES.get(name.lower().strip(), "")
    if "/" in alias:  # a command, e.g. the settings menu
        subprocess.Popen([alias], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"opened {name}"
    found = find_app(name)
    if not found:
        return f'no app matches "{name}": {name} is not installed. Tell the user plainly that it is not installed.'
    app_id, app_name, command = found[1]
    launch = ["kitty", "--title", app_name, "sh", "-c", command] if command else ["gtk-launch", app_id]
    subprocess.Popen(launch, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opened {app_name}"


def open_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    subprocess.Popen(["flatpak", "run", "com.google.Chrome", url], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opened {url}"


# Site search pages, checked with curl (each returns the search results page).
# Other sites use a Google search limited to that site, which always works.
SEARCH_URLS = {
    "google": "https://www.google.com/search?q={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "deviantart": "https://www.deviantart.com/search?q={}",
    "github": "https://github.com/search?q={}",
    "pinterest": "https://www.pinterest.com/search/pins/?q={}",
    "archwiki": "https://wiki.archlinux.org/index.php?search={}",
    "aur": "https://aur.archlinux.org/packages?K={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
}
SITE_ALIASES = {"wiki": "wikipedia", "yt": "youtube", "deviant art": "deviantart", "devient art": "deviantart",
                "da": "deviantart", "arch wiki": "archwiki", "ddg": "duckduckgo", "web": "google", "": "google"}


def web_search(query, site=""):
    """Search the web, or one site, in a new Chrome tab."""
    key = re.sub(r"\.(com|org|net|io|in)$", "", str(site).lower().strip().removeprefix("www."))
    key = SITE_ALIASES.get(key, key.replace(" ", ""))
    q = urllib.parse.quote_plus(str(query).strip())
    if key in SEARCH_URLS:
        url = SEARCH_URLS[key].format(q)
    else:  # unknown site: Google, limited to that site
        domain = key if "." in key else f"{key}.com"
        url = SEARCH_URLS["google"].format(q + urllib.parse.quote_plus(f" site:{domain}"))
    return open_url(url)


def open_or_switch(chrome, url):
    """A plain site address (no path, no search): switch to an open tab of that exact host.
    Anything else (a search, a page) opens a new tab."""
    m = re.match(r"^(?:https?://)?([^/?#]+)/?$", url.strip())
    if m:
        host = m.group(1).lower().removeprefix("www.")
        same = [t for t in (chrome.find([host]) or [])
                if re.sub(r"^https?://(www\.)?", "", t["url"]).split("/")[0].lower() == host]
        if same:
            return chrome.switch_tab(str(same[0]["id"]))
    return open_url(url)


# ---------- system settings (small and reversible) ----------

def set_volume(percent):
    """percent: a number (40), or a step: '+10' louder, '-10' softer."""
    value = str(percent).strip().rstrip("%")
    if value.startswith(("+", "-")):
        step = f"{abs(int(float(value)))}%{'+' if value[0] == '+' else '-'}"
        return sh("wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", step) or f"volume {value}%"
    return sh("wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", f"{int(float(value))}%") or f"volume {value}%"


def set_brightness(percent):
    return sh("brightnessctl", "set", f"{int(percent)}%")


def toggle(kind, on):
    on = str(on).lower() in ("true", "on", "1", "yes")
    cmds = {
        "wifi": ["nmcli", "radio", "wifi", "on" if on else "off"],
        "bluetooth": ["bluetoothctl", "power", "on" if on else "off"],
        "night_light": ["hyprctl", "hyprsunset", "temperature", "4500"] if on else ["hyprctl", "hyprsunset", "identity"],
        "do_not_disturb": ["swaync-client", "-dn" if on else "-df"],
    }
    if kind not in cmds:
        return f"unknown setting {kind}"
    sh(*cmds[kind])
    return f"{kind} {'on' if on else 'off'}"


def power_profile(profile):
    return sh("powerprofilesctl", "set", profile) or f"power profile {profile}"


# ---------- diagnostics (read only) ----------

def read(path, default="?"):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def gib(n_bytes):
    return f"{n_bytes / 2**30:.1f} GiB"


def memory_usage():
    info = dict(line.split(":", 1) for line in read("/proc/meminfo", "").splitlines() if ":" in line)
    total = int(info["MemTotal"].split()[0]) * 1024
    available = int(info["MemAvailable"].split()[0]) * 1024
    return f"{gib(total - available)} used of {gib(total)}"


def temperatures():
    rows = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        temp = read(zone / "temp", "")
        if temp.isdigit():
            rows.append(f"  {read(zone / 'type')}: {int(temp) // 1000} C")
    return "\n".join(rows) or "  none found"


def system_status():
    bat = next(Path("/sys/class/power_supply").glob("BAT*"), Path("/nonexistent"))
    disk = shutil.disk_usage("/")
    return "\n".join([
        f"battery: {read(bat / 'capacity')}% ({read(bat / 'status')})",
        f"power profile: {sh('powerprofilesctl', 'get')}",
        f"memory: {memory_usage()}",
        f"disk /: {gib(disk.used)} used of {gib(disk.total)}",
        f"load: {read('/proc/loadavg')}",
        f"uptime: {sh('uptime', '-p')}",
        f"temperatures:\n{temperatures()}",
        f"NVIDIA GPU: {read('/sys/bus/pci/devices/0000:01:00.0/power/runtime_status', 'not found on the PCI bus')}",
    ])


def check_errors():
    failed = sh("systemctl", "--failed", "--no-legend", "--plain") or "no failed system services"
    user_failed = sh("systemctl", "--user", "--failed", "--no-legend", "--plain") or "no failed user services"
    errors = sh("journalctl", "-p", "err", "--since", "-1h", "--no-pager", "-o", "short", "-n", "15") or "no errors in the last hour"
    return f"{failed}\n{user_failed}\nrecent errors:\n{errors}"


def network_status():
    return sh("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device") + "\n" + \
        sh("sh", "-c", "ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 && echo internet: ok || echo internet: no reply")


def bluetooth_status():
    return sh("bluetoothctl", "devices", "Connected") or "no Bluetooth devices connected"


# ---------- terminal (visible to the user) ----------

# Commands that can change or delete things: the user is asked first.
RISKY = re.compile(r"(^|[;&|`(]\s*)(rm|rmdir|dd|mkfs\S*|shred|truncate|chmod|chown|mv|cp|ln|kill|pkill|killall|"
                   r"reboot|poweroff|shutdown|systemctl|pacman|yay|paru|flatpak|pip|npm|git\s+(push|reset|clean|checkout)"
                   r"|crontab|wipefs|parted|fdisk)\b|>|curl[^|]*\|\s*(ba)?sh|wget[^|]*\|\s*(ba)?sh")
NEEDS_ROOT = re.compile(r"\b(sudo|su|doas|pkexec)\b")
# Commands that would destroy the system or the home folder: never run, never even ask.
CATASTROPHIC = re.compile(
    r"\brm\s+(-\w*\s+)*(-\w*[rR]\w*\s+)(-\w*\s+)*(~/?|/|/home/?|/home/\w+/?|\$HOME/?|\*|\.\.?/?)(\s|$)"
    r"|\bmkfs|\bwipefs\b|\bdd\b.*\bof=/dev/|\bchmod\s+-R\s+\S+\s+/(\s|$)|:\(\)\s*\{\s*:\|:&\s*\};:")


def command_is_risky(command):
    # catastrophic commands are refused in run_in_terminal, so they never reach a yes/no question
    return bool(RISKY.search(command)) and not CATASTROPHIC.search(command)


def run_in_terminal(command):
    """Open Kitty, run the command, and keep the window open with a shell afterwards."""
    if re.match(r"^\s*claude\b", command):  # Claude Code windows get a socket, so she can type into them
        prompt = re.sub(r"^\s*claude\s*", "", command).strip().strip("'\"")
        return escalate.open_claude(prompt)
    if command.strip().lower() in ("", "kitty", "terminal", "zsh", "bash", "shell"):
        subprocess.Popen(["kitty"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "opened a Kitty terminal"
    if CATASTROPHIC.search(command):
        return ("REFUSED: this command would destroy the home folder or the system. "
                "Do not run it, do not ask again, and tell the user plainly that you will not do this.")
    if NEEDS_ROOT.search(command):
        return "This needs root rights. Do not run it: call ask_claude with the task instead."
    subprocess.Popen(["kitty", "--title", f"Castorice: {command[:60]}", "zsh", "-ic", f"{command}; exec zsh"],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opened a Kitty window and ran: {command}"


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


def find_files(words, kind="any"):
    """Search the home folder by name with fd. Newest first, at most 20."""
    # --full-path: the words may be in a folder name too ("wallpaper" finds ~/Pictures/wallpaper/x.jpg)
    cmd = ["fd", "--ignore-case", "--absolute-path", "--full-path", "--exclude", ".cache", "--exclude", ".local/share/Trash",
           "--max-results", "200"]
    if kind == "folder":
        cmd += ["--type", "d"]
    else:
        cmd += ["--type", "f"] + [arg for ext in KINDS.get(kind, []) for arg in ("--extension", ext)]
    pattern = ".*".join(re.escape(w) for w in str(words).split()) or "."
    out = sh(*cmd, pattern, str(HOME), timeout=20)
    paths = [Path(p) for p in out.splitlines() if p.startswith("/") and "/.local/share/Trash" not in p]
    if kind == "folder":  # shallow folders first: "pictures" means ~/Pictures, not a folder deep inside
        paths.sort(key=lambda p: len(p.parts))
        return "\n".join(str(p).replace(str(HOME), "~", 1) for p in paths[:20]) or f'no folder matches "{words}"'
    if not paths:
        return f'no {kind if kind != "any" else ""} files match "{words}" in the home folder'
    paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    rows = []
    for p in paths[:20]:
        when = time_ago(p.stat().st_mtime) if p.exists() else "?"
        rows.append(f"{str(p).replace(str(HOME), '~', 1)}  ({when})")
    more = f"\n... and {len(paths) - 20} more" if len(paths) > 20 else ""
    return "\n".join(rows) + more


def fix_home(path):
    """Map an invented home folder (/home/<name>/...) to the real one."""
    path = os.path.expanduser(str(path).strip())
    return re.sub(r"^/home/[^/]+", str(HOME), path) if path.startswith("/home/") else path


def resolve(path):
    p = Path(fix_home(path))
    return p if p.exists() else None


def open_file(path):
    p = resolve(path)
    if not p:
        return f"{path} does not exist"
    subprocess.Popen(["xdg-open", str(p)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opened {p.name}"


def show_in_file_manager(path):
    p = resolve(path)
    if not p:
        return f"{path} does not exist"
    folder = p if p.is_dir() else p.parent
    subprocess.Popen(["pcmanfm-qt", str(folder)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"opened the folder {folder}"


def time_ago(timestamp):
    seconds = max(0, time.time() - timestamp)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"


# ---------- security ----------

def security_check():
    """Known security holes in installed packages (arch-audit), plus the health check."""
    holes = sh("arch-audit", "--upgradable", "--format", "%n %s %c", timeout=60)
    all_holes = sh("arch-audit", "--format", "%n", timeout=60)
    n_all = len([l for l in all_holes.splitlines() if l.strip()])
    fixable = holes or "none"
    return (f"packages with known security holes: {n_all}\n"
            f"fixed by an update now (run sysupdate): {fixable}\n\nhealth check:\n"
            + sh(str(HOME / "dotfiles/bin/health"), timeout=60))


def virus_scan(folder="~/Downloads"):
    """Scan a folder with ClamAV. Read only: nothing is deleted or moved."""
    p = resolve(folder)
    if not p:
        return f"{folder} does not exist"
    out = sh("clamscan", "--recursive", "--infected", "--suppress-ok-results", str(p), timeout=1800)
    summary = [l for l in out.splitlines() if l.startswith(("Scanned files", "Infected files", "Data scanned", "Time"))]
    found = [l for l in out.splitlines() if l.endswith("FOUND")]
    if not summary:
        return f"the scan did not finish: {out[-300:]}"
    return "\n".join(summary + (["infected:"] + found if found else ["nothing found"]))


# ---------- memory ----------

def load_memory():
    try:
        return json.loads(MEMORY_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def remember(fact):
    facts = load_memory()
    if fact not in facts:
        facts = (facts + [fact])[-50:]  # keep the newest 50
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(facts, indent=1))
    return "remembered"


def recall(words):
    hits = [f for f in load_memory() if any(w.lower() in f.lower() for w in str(words).split())]
    return "\n".join(hits) or "nothing in memory about that"


def forget(words):
    keep = [f for f in load_memory() if not any(w.lower() in f.lower() for w in str(words).split())]
    removed = len(load_memory()) - len(keep)
    MEMORY_FILE.write_text(json.dumps(keep, indent=1))
    return f"forgot {removed} memories"


def preview_forget(words):
    hits = [f for f in load_memory() if any(w.lower() in f.lower() for w in str(words).split())]
    if not hits:
        return False, "nothing in memory matches that"
    return True, f"forget these {len(hits)} memories: " + "; ".join(h[:60] for h in hits[:5])


def time_now():
    return sh("date", "+%A %d %B %Y, %H:%M")


# ---------- registry ----------

def build_tools(chrome):
    """Return {name: Tool}. chrome is a ChromeBridge (tab tools)."""
    s = {"type": "string"}
    n = {"type": "number"}
    w = {"window": {**s, "description": "part of the window class or title, e.g. chrome, kitty"}}
    tools = [
        Tool("list_windows", TIER_READ, "List open windows.", {}, [], list_windows),
        Tool("focus_window", TIER_SMALL, "Bring a window to the front. Use a class or title word from list_windows.", w, ["window"],
             window_action('hl.dsp.focus({{ window = "{sel}" }})')),
        Tool("minimize_window", TIER_SMALL, "Minimize a window (it stays in the taskbar).", w, ["window"],
             window_action('function() hl.dispatch(hl.dsp.window.move({{ window = "{sel}", workspace = "special:minimized", follow = false }})) end')),
        Tool("move_window", TIER_SMALL, "Move a window to workspace 1-10.",
             {**w, "workspace": n}, ["window", "workspace"], move_window),
        Tool("close_window", TIER_CONFIRM, "Close a window.", w, ["window"],
             window_action('hl.dsp.window.close({{ window = "{sel}" }})'), preview=describe_window),
        Tool("open_app", TIER_SMALL, "Open an app by name.", {"name": s}, ["name"], open_app),
        Tool("web_search", TIER_SMALL, "Search the web or one site (wikipedia, youtube, deviantart, github, "
             "reddit, amazon, ...) in a new Chrome tab. Use this for every search; never build search URLs yourself.",
             {"query": s, "site": {"type": "string", "description": "site name, or empty for Google"}},
             ["query"], web_search),
        Tool("open_url", TIER_SMALL, "Open a web page in Chrome (switches to it if a tab is already open).",
             {"url": s}, ["url"], lambda url: open_or_switch(chrome, url)),
        Tool("set_volume", TIER_SMALL, "Set the volume: a number 0-100, or '+10' louder, '-10' softer.",
             {"percent": s}, ["percent"], set_volume),
        Tool("set_brightness", TIER_SMALL, "Set the screen brightness, 1-100.", {"percent": n}, ["percent"], set_brightness),
        Tool("toggle", TIER_SMALL, "Turn a setting on or off.",
             {"kind": {**s, "enum": ["wifi", "bluetooth", "night_light", "do_not_disturb"]}, "on": {"type": "boolean"}},
             ["kind", "on"], toggle),
        Tool("power_profile", TIER_SMALL, "Set the power profile.",
             {"profile": {**s, "enum": ["power-saver", "balanced", "performance"]}}, ["profile"], power_profile),
        Tool("system_status", TIER_READ, "Battery, memory, disk, temperatures, GPU state.", {}, [], system_status),
        Tool("check_errors", TIER_READ, "Failed services and system errors of the last hour.", {}, [], check_errors),
        Tool("network_status", TIER_READ, "Network devices and internet reachability.", {}, [], network_status),
        Tool("bluetooth_status", TIER_READ, "Connected Bluetooth devices.", {}, [], bluetooth_status),
        Tool("health_check", TIER_READ, "Full system health check: services, GPU, Hyprland, plugin, disk, "
             "updates, dotfiles. Use when the user asks if everything is ok.", {}, [],
             lambda: sh(str(Path.home() / "dotfiles/bin/health"), timeout=60)),
        Tool("run_in_terminal", TIER_SMALL, "Open a Kitty terminal and run a command in it, visible to the user. "
             "Example: 'open kitty and run claude' -> command='claude'. Never use sudo.",
             {"command": s}, ["command"], run_in_terminal, needs_confirm=lambda command: command_is_risky(command),
             preview=lambda command: (True, f"run this command in a terminal: {command}")),
        Tool("find_files", TIER_READ, "Find files or folders in the home folder by words in their names.",
             {"words": s, "kind": {**s, "enum": ["any", "document", "image", "video", "audio", "code", "archive", "folder"]}},
             ["words"], find_files),
        Tool("open_file", TIER_SMALL, "Open a file with its default app. Use a path from find_files.",
             {"path": s}, ["path"], open_file),
        Tool("show_in_file_manager", TIER_SMALL, "Open a folder (or the folder of a file) in the file manager. "
             "Common folders: ~/Pictures, ~/Downloads, ~/Documents, ~/Desktop, ~/Music, ~/Videos, ~/dotfiles.",
             {"path": s}, ["path"], show_in_file_manager),
        Tool("security_check", TIER_READ, "Security check: installed packages with known security holes, and the health check.",
             {}, [], security_check),
        Tool("virus_scan", TIER_READ, "Scan a folder for viruses with ClamAV (slow; default ~/Downloads). Nothing is deleted.",
             {"folder": s}, [], virus_scan),
        Tool("recall", TIER_READ, "Search your memories about the user.", {"words": s}, ["words"], recall),
        Tool("forget", TIER_CONFIRM, "Forget memories that contain these words.", {"words": s}, ["words"], forget,
             preview=preview_forget),
        Tool("time_now", TIER_READ, "The current date and time.", {}, [], time_now),
        Tool("remember", TIER_READ, "Save a fact about the user to long-term memory.", {"fact": s}, ["fact"], remember),
        Tool("list_tabs", TIER_READ, "List open Chrome tabs (title | url, * = active).", {}, [], chrome.list_tabs),
        Tool("switch_tab", TIER_SMALL, "Switch to the Chrome tab whose title or URL contains a word.",
             {"tab": {**s, "description": "a word from the tab title or URL"}}, ["tab"], chrome.switch_tab),
        Tool("open_tab", TIER_SMALL, "Open a new Chrome tab.", {"url": s}, ["url"], chrome.open_tab),
        Tool("group_tabs", TIER_SMALL, "Put Chrome tabs into a named group.",
             {**{"tabs": {"type": "array", "items": s, "description": "words from the tab titles or URLs, e.g. [\"youtube\", \"whatsapp\"]"}}, "title": s}, ["tabs", "title"], chrome.group_tabs),
        Tool("close_tabs", TIER_CONFIRM, "Close Chrome tabs. Name them by words from their titles or URLs. "
             "For 'all except X': tabs=[\"all\"], keep=[\"X\"].",
             {"tabs": {"type": "array", "items": s, "description": "words from the tab titles or URLs, or [\"all\"]"},
              "keep": {"type": "array", "items": s, "description": "tabs to keep open (optional)"}},
             ["tabs"], chrome.close_tabs, preview=lambda tabs, keep=(): chrome.describe(tabs, keep)),
        Tool("tell_claude", TIER_SMALL, "Talk to Claude Code: types the message into the open Claude Code "
             "window and presses Enter (opens Claude Code with the message if none is open).",
             {"message": s}, ["message"], lambda message: escalate.tell_claude(message)),
        Tool("ask_claude", "2", "Hand a big or risky task to Claude Code: installing or removing software, "
             "editing config files, services, deleting files, anything that needs sudo, or anything you are unsure about.",
             {"task": {**s, "description": "the full task, with what you already found out"}}, ["task"], None),
    ]
    return {t.name: t for t in tools}


def ollama_schema(tools):
    return [{"type": "function", "function": {
        "name": t.name, "description": t.description,
        "parameters": {"type": "object", "properties": t.params, "required": t.required}}}
        for t in tools.values()]
