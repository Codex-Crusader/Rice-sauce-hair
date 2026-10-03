"""System settings, diagnostics, the terminal, and the security checks."""
import re
import shutil
import threading
import time
from pathlib import Path

import handoff
from policy import TERMINAL_ONLY, PathRefused, is_claude_command, safe_path
from runner import Result
from tools.common import act, spawn


# ---------- system settings (small and reversible) ----------

def set_volume(runner, percent):
    """percent: a number (40), or a step: '+10' louder, '-10' softer."""
    value = str(percent).strip().rstrip("%")
    if value.startswith(("+", "-")):
        step = f"{abs(int(float(value)))}%{'+' if value[0] == '+' else '-'}"
        return act(runner, ["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", step], f"volume {value}%")
    return act(runner, ["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", f"{int(float(value))}%"],
               f"volume {value}%")


def set_brightness(runner, percent):
    percent = max(1, min(100, int(float(percent))))  # 0 turns the screen off
    return act(runner, ["brightnessctl", "set", f"{percent}%"], f"brightness {percent}%")


def toggle(runner, kind, on):
    on = str(on).lower() in ("true", "on", "1", "yes")
    kind = re.sub(r"[\s-]+", "_", str(kind).strip().lower())  # "night light" -> night_light
    cmds = {
        "wifi": ["nmcli", "radio", "wifi", "on" if on else "off"],
        "bluetooth": ["bluetoothctl", "power", "on" if on else "off"],
        "night_light": ["hyprctl", "hyprsunset", "temperature", "4500"] if on else ["hyprctl", "hyprsunset", "identity"],
        "do_not_disturb": ["swaync-client", "-dn" if on else "-df"],
    }
    if kind not in cmds:
        return Result(False, f"unknown setting {kind}")
    return act(runner, cmds[kind], f"{kind} {'on' if on else 'off'}")


def power_profile(runner, profile):
    return act(runner, ["powerprofilesctl", "set", profile], f"power profile {profile}")


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


def system_status(runner):
    bat = next(Path("/sys/class/power_supply").glob("BAT*"), Path("/nonexistent"))
    disk = shutil.disk_usage("/")
    return Result(True, "\n".join([
        f"battery: {read(bat / 'capacity')}% ({read(bat / 'status')})",
        f"power profile: {runner.run(['powerprofilesctl', 'get']).text}",
        f"memory: {memory_usage()}",
        f"disk /: {gib(disk.used)} used of {gib(disk.total)}",
        f"load: {read('/proc/loadavg')}",
        f"uptime: {runner.run(['uptime', '-p']).text}",
        f"temperatures:\n{temperatures()}",
        f"NVIDIA GPU: {read('/sys/bus/pci/devices/0000:01:00.0/power/runtime_status', 'not found on the PCI bus')}",
    ]))


def check_errors(runner):
    failed = runner.run(["systemctl", "--failed", "--no-legend", "--plain"]).text or "no failed system services"
    user_failed = runner.run(["systemctl", "--user", "--failed", "--no-legend", "--plain"]).text or "no failed user services"
    errors = runner.run(["journalctl", "-p", "err", "--since", "-1h", "--no-pager", "-o", "short", "-n", "15"]).text \
        or "no errors in the last hour"
    return Result(True, f"{failed}\n{user_failed}\nrecent errors:\n{errors}")


def network_status(runner):
    devices = runner.run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).text
    online = runner.run(["ping", "-c1", "-W2", "1.1.1.1"]).ok
    return Result(True, f"{devices}\ninternet: {'ok' if online else 'no reply'}")


def bluetooth_status(runner):
    return Result(True, runner.run(["bluetoothctl", "devices", "Connected"]).text or "no Bluetooth devices connected")


def health_check(runner, repo):
    r = runner.run([str(repo / "bin/health")], timeout=60)
    return Result(True, r.text)  # health exits 0 or 1; its WARN lines say what is wrong


# ---------- terminal (visible to the user) ----------

def run_in_terminal(runner, command):
    """Open Kitty, run the command, and keep the window open with a shell afterwards.
    policy.command_verdict decides first if the command may run."""
    if is_claude_command(command):  # Claude Code windows get a socket, so she can type into them
        prompt = re.sub(r"^\s*claude\s*", "", command).strip().strip("'\"")
        return handoff.open_window(runner, prompt)
    if command.strip().lower() in TERMINAL_ONLY:
        return spawn(runner, ["kitty"], "opened a Kitty terminal")
    return spawn(runner, ["kitty", "--title", f"Companion: {command[:60]}", "zsh", "-ic", f"{command}; exec zsh"],
                 f"opened a Kitty window and ran: {command}")


# ---------- security ----------

def security_check(runner, repo):
    """Known security holes in installed packages (arch-audit), plus the health check."""
    if shutil.which("arch-audit"):
        all_holes = runner.run(["arch-audit", "--format", "%n"], timeout=60)
        fixable = runner.run(["arch-audit", "--upgradable", "--format", "%n %s %c"], timeout=60).text or "none"
        n_all = len([l for l in all_holes.text.splitlines() if l.strip()]) if all_holes.ok else "unknown (arch-audit failed)"
        holes = f"packages with known security holes: {n_all}\nfixed by an update now (run sysupdate): {fixable}"
    else:
        holes = "arch-audit is not installed, so the package check did not run"
    return Result(True, holes + "\n\nhealth check:\n" + health_check(runner, repo).text)


# The virus scan runs in the background, so she stays free to talk. scan["on_done"](text) gets the result.
scan = {"running": False, "on_done": None}


def virus_scan(runner, deny, folder="~/Downloads"):
    """Start a ClamAV scan of a folder in the home folder. Read only: nothing is deleted or moved."""
    try:
        p = safe_path(folder, deny)
    except PathRefused as e:
        return Result(False, f"refused: {e}. Tell the user plainly.", final=True)
    if scan["running"]:
        return Result(False, "failed: a virus scan is already running. Call stop_virus_scan to stop it.")
    scan["running"] = True
    threading.Thread(target=_scan, args=(runner, p), daemon=True).start()
    return Result(True, f"the virus scan of {p} started in the background. "
                        f"Tell the user you will say the result when it is done.")


def _scan(runner, folder):
    r = runner.run(["clamscan", "--recursive", "--infected", "--suppress-ok-results", str(folder)], timeout=1800)
    scan["running"] = False
    lines = r.text.splitlines()
    summary = [l for l in lines if l.startswith(("Scanned files", "Infected files", "Data scanned", "Time"))]
    found = [l for l in lines if l.endswith("FOUND")]
    if not summary:  # clamscan exits 1 when it finds a virus, so the summary decides, not the exit code
        result = f"the virus scan did not finish: {r.text[-300:]}"
    else:
        result = "\n".join(summary + (["infected:"] + found if found else ["nothing found"]))
    if scan["on_done"]:
        scan["on_done"](result)


def stop_virus_scan(runner):
    if not scan["running"]:
        return Result(False, "no virus scan is running", final=True)
    runner.run(["pkill", "-x", "clamscan"])
    return Result(True, "stopped the virus scan")


def time_now():
    return Result(True, time.strftime("%A %d %B %Y, %H:%M"))
