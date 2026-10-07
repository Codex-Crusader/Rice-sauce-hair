"""Tools that Companion can use.

Each tool has a tier (see policy.py, which makes every safety decision):
  0  read only            runs at once
  1  small, reversible    runs at once, she says what she did
  1b closes something     she asks "yes or no?" first
  anything bigger         not a tool: the planner hands it to Claude Code (handoff.py)
A tool only does its action. It makes no safety decision, with one exception: the file tools
call policy.safe_path themselves, so the home-folder boundary holds for every caller.

Every tool returns a Result. Tools that run outside commands get a Runner as their
first parameter (build_tools binds it), so a test can give them a fake runner.
"""
from functools import partial
from pathlib import Path

import handoff
from policy import TIER_CONFIRM, TIER_READ, TIER_SMALL
from tools import apps, browser, files, memory, system, windows
from tools.apps import APP_ALIASES, app_names, find_app  # noqa: F401  (the brain uses these)
from tools.common import Tool
from tools.system import scan  # noqa: F401  (main.py sets scan["on_done"])

# ---------- registry ----------

def build_tools(chrome, runner, config, store):
    """Return {name: Tool}. chrome is a ChromeBridge (tab tools), runner runs outside commands."""
    r, repo, deny = runner, config.repo, config.deny_paths
    quarantine = config.data_dir / "quarantine"
    home_repo = "~/" + str(repo.relative_to(Path.home())) if repo.is_relative_to(Path.home()) else str(repo)
    s = {"type": "string"}
    n = {"type": "number"}
    w = {"window": {**s, "description": "part of the window class or title, e.g. chrome, kitty"}}
    tools = [
        Tool("list_windows", TIER_READ, "List open windows.", {}, [], partial(windows.list_windows, r)),
        Tool("focus_window", TIER_SMALL, "Bring a window to the front. Use a class or title word from list_windows.", w, ["window"],
             partial(windows.window_action('hl.dsp.focus({{ window = "{sel}" }})'), r)),
        Tool("minimize_window", TIER_SMALL, "Minimize a window (it stays in the taskbar).", w, ["window"],
             partial(windows.window_action('function() hl.dispatch(hl.dsp.window.move({{ window = "{sel}", workspace = "special:minimized", follow = false }})) end'), r)),
        Tool("move_window", TIER_SMALL, "Move a window to workspace 1-10.",
             {**w, "workspace": n}, ["window", "workspace"], partial(windows.move_window, r)),
        Tool("close_window", TIER_CONFIRM, "Close a window.", w, ["window"],
             partial(windows.window_action('hl.dsp.window.close({{ window = "{sel}" }})'), r), preview=partial(windows.describe_window, r)),
        Tool("open_app", TIER_SMALL, "Open an app by name.", {"name": s}, ["name"], partial(apps.open_app, r, repo, store)),
        Tool("web_search", TIER_SMALL, "Search the web or one site (wikipedia, youtube, deviantart, github, "
             "reddit, amazon, ...) in a new Chrome tab. Use this for every search; never build search URLs yourself.",
             {"query": s, "site": {"type": "string", "description": "site name, or empty for Google"}},
             ["query"], partial(browser.web_search, r)),
        Tool("open_url", TIER_SMALL, "Open a web page in Chrome (switches to it if a tab is already open).",
             {"url": s}, ["url"], partial(browser.open_or_switch, r, chrome)),
        Tool("set_volume", TIER_SMALL, "Set the volume: a number 0-100, or '+10' louder, '-10' softer.",
             {"percent": s}, ["percent"], partial(system.set_volume, r)),
        Tool("set_brightness", TIER_SMALL, "Set the screen brightness, 1-100.", {"percent": n}, ["percent"],
             partial(system.set_brightness, r)),
        Tool("toggle", TIER_SMALL, "Turn a setting on or off.",
             {"kind": {**s, "enum": ["wifi", "bluetooth", "night_light", "do_not_disturb"]}, "on": {"type": "boolean"}},
             ["kind", "on"], partial(system.toggle, r)),
        Tool("power_profile", TIER_SMALL, "Set the power profile.",
             {"profile": {**s, "enum": ["power-saver", "balanced", "performance"]}}, ["profile"], partial(system.power_profile, r)),
        Tool("system_status", TIER_READ, "Battery, memory, disk, temperatures, GPU state.", {}, [], partial(system.system_status, r)),
        Tool("check_errors", TIER_READ, "Failed services and system errors of the last hour.", {}, [], partial(system.check_errors, r)),
        Tool("network_status", TIER_READ, "Network devices and internet reachability.", {}, [], partial(system.network_status, r)),
        Tool("bluetooth_status", TIER_READ, "Connected Bluetooth devices.", {}, [], partial(system.bluetooth_status, r)),
        Tool("health_check", TIER_READ, "Full system health check: services, GPU, Hyprland, plugin, disk, "
             "updates, dotfiles. Use when the user asks if everything is ok.", {}, [], partial(system.health_check, r, repo)),
        Tool("run_in_terminal", TIER_SMALL, "Open a Kitty terminal and run a command in it, visible to the user. "
             "Example: 'open kitty and run claude' -> command='claude'. Never use sudo.",
             {"command": s}, ["command"], partial(system.run_in_terminal, r),
             preview=lambda command: (True, f"run this command in a terminal: {command}")),
        Tool("find_files", TIER_READ, "Find files or folders in the home folder by words in their names.",
             {"words": s, "kind": {**s, "enum": ["any", "document", "image", "video", "audio", "code", "archive", "folder"]}},
             ["words"], partial(files.find_files, r)),
        Tool("open_file", TIER_SMALL, "Open a file with its default app. Use a path from find_files.",
             {"path": s}, ["path"], partial(files.open_file, r, deny)),
        Tool("show_in_file_manager", TIER_SMALL, "Open a folder (or the folder of a file) in the file manager. "
             f"Common folders: ~/Pictures, ~/Downloads, ~/Documents, ~/Desktop, ~/Music, ~/Videos, {home_repo}.",
             {"path": s}, ["path"], partial(files.show_in_file_manager, r, deny)),
        Tool("security_check", TIER_READ, "Security check: installed packages with known security holes, and the health check.",
             {}, [], partial(system.security_check, r, repo)),
        Tool("virus_scan", TIER_SMALL, "Start a virus scan of a folder with ClamAV, in the background (default "
             "~/Downloads). Found files move to the quarantine (nothing is deleted). The result comes later on its own.",
             {"folder": s}, [], partial(system.virus_scan, r, deny, quarantine)),
        Tool("list_quarantine", TIER_READ, "List the files that a virus scan moved to the quarantine.", {}, [],
             partial(system.list_quarantine, quarantine)),
        Tool("restore_from_quarantine", TIER_CONFIRM, "Put one quarantined file back where it was (for a false alarm). "
             "Use a name from list_quarantine.", {"name": s}, ["name"], partial(system.restore_from_quarantine, quarantine, deny),
             preview=partial(system.preview_restore, quarantine)),
        Tool("empty_quarantine", TIER_CONFIRM, "Delete all quarantined files for good.", {}, [],
             partial(system.empty_quarantine, quarantine), preview=partial(system.preview_empty, quarantine)),
        Tool("stop_virus_scan", TIER_SMALL, "Stop the running virus scan.", {}, [], partial(system.stop_virus_scan, r)),
        Tool("recall", TIER_READ, "Search your memories about the user.", {"words": s}, ["words"], partial(memory.recall, store)),
        Tool("forget", TIER_CONFIRM, "Forget memories that contain these words.", {"words": s}, ["words"], partial(memory.forget, store),
             preview=partial(memory.preview_forget, store)),
        Tool("time_now", TIER_READ, "The current date and time.", {}, [], system.time_now),
        Tool("remember", TIER_SMALL, "Save a fact about the user to long-term memory.", {"fact": s}, ["fact"], partial(memory.remember, store),
             preview=lambda fact: (True, f'remember this: "{fact}"')),
        Tool("list_tabs", TIER_READ, "List open Chrome tabs (title | url, * = active).", {}, [], chrome.list_tabs),
        Tool("switch_tab", TIER_SMALL, "Switch to the Chrome tab whose title or URL contains a word.",
             {"tab": {**s, "description": "a word from the tab title or URL"}}, ["tab"], chrome.switch_tab),
        Tool("open_tab", TIER_SMALL, "Open a new Chrome tab.", {"url": s}, ["url"], chrome.open_tab),
        Tool("group_tabs", TIER_SMALL, "Put Chrome tabs into a named group.",
             {"tabs": {"type": "array", "items": s, "description": "words from the tab titles or URLs, e.g. [\"youtube\", \"whatsapp\"]"}, "title": s}, ["tabs", "title"], chrome.group_tabs),
        Tool("close_tabs", TIER_CONFIRM, "Close Chrome tabs. Name them by words from their titles or URLs. "
             "For 'all except X': tabs=[\"all\"], keep=[\"X\"].",
             {"tabs": {"type": "array", "items": s, "description": "words from the tab titles or URLs, or [\"all\"]"},
              "keep": {"type": "array", "items": s, "description": "tabs to keep open (optional)"}},
             ["tabs"], chrome.close_tabs, preview=lambda tabs, keep=(): chrome.describe(tabs, keep)),
        Tool("tell_claude", TIER_SMALL, "Talk to Claude Code: types the message into the open Claude Code "
             "window and presses Enter (opens Claude Code with the message if none is open).",
             {"message": s}, ["message"], partial(handoff.type_into_window, r),
             preview=lambda message: (True, f'type this into Claude Code: "{message}"')),
    ]
    return {t.name: t for t in tools}


def ollama_schema(tools):
    return [{"type": "function", "function": {
        "name": t.name, "description": t.description,
        "parameters": {"type": "object", "properties": t.params, "required": t.required}}}
        for t in tools.values()]
