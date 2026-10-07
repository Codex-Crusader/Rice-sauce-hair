"""System settings, diagnostics, the terminal, and the security checks."""
import json
import re
import secrets
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
# A found file is not deleted: it moves to the quarantine folder, read only, with a record of where it was.
# Restore and permanent delete are separate tools that ask first (tier 1b).
scan = {"running": False, "on_done": None}
RECORDS = "records.json"


def _posix_regex(path):
    return "^" + re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", str(path))


def virus_scan(runner, deny, quarantine, folder="~/Downloads"):
    """Start a ClamAV scan of a folder in the home folder. Found files move to the quarantine."""
    try:
        p = safe_path(folder, deny)
    except PathRefused as e:
        return Result(False, f"refused: {e}. Tell the user plainly.", final=True)
    if not shutil.which("clamscan"):
        return Result(False, "ClamAV is not installed, so there is no virus scan. To install it: sudo pacman -S clamav, "
                             "then the virus signature steps in docs/INSTALL.md (step 5).", final=True)
    if scan["running"]:
        return Result(False, "failed: a virus scan is already running. Call stop_virus_scan to stop it.")
    scan["running"] = True
    threading.Thread(target=_scan, args=(runner, p, deny, Path(quarantine)), daemon=True).start()
    return Result(True, f"the virus scan of {p} started in the background. "
                        f"Tell the user you will say the result when it is done.")


def _scan(runner, folder, deny, quarantine):
    try:
        result = _scan_and_move(runner, folder, deny, quarantine)
    except Exception as e:  # noqa: BLE001  (she must always hear that the scan ended)
        result = f"the virus scan failed: {e}"
    finally:
        scan["running"] = False
    _log(quarantine.parent / "virus-scans.log", folder, result)
    if scan["on_done"]:
        scan["on_done"](result)


def _found(text):
    """[(path, signature)] from clamscan output lines "path: Signature FOUND"."""
    return [tuple(l.removesuffix(" FOUND").rsplit(": ", 1)) for l in text.splitlines() if l.endswith(" FOUND") and ": " in l]


def _scan_and_move(runner, folder, deny, quarantine):
    skip = [f"--exclude-dir={_posix_regex(d)}" for d in [*deny, quarantine]]
    r = runner.run(["clamscan", "--recursive", "--infected", "--suppress-ok-results", *skip, str(folder)], timeout=3600)
    summary = [l for l in r.text.splitlines() if l.startswith(("Scanned files", "Infected files", "Data scanned", "Time"))]
    if not summary:  # clamscan exits 1 when it finds a virus, so the summary decides, not the exit code
        return f"the virus scan did not finish: {r.text[-300:]}"
    infected = int(next((l.split(":")[1] for l in summary if l.startswith("Infected files")), "0") or 0)
    found = _found(r.text)
    lines = list(summary)
    if found:
        # A file name with a line break can fake a FOUND line for another file: scan each named file again.
        # A faked path cannot start with "/" (no "/" in a name), so only real paths reach the second scan,
        # never a faked option such as --log=<file>.
        inside = str(folder).rstrip("/") + "/"
        real = [path for path, _ in found if path.startswith(inside)]
        check = runner.run(["clamscan", "--no-summary", "--infected", *real], timeout=600) if real else Result(True, "")
        confirmed = {path for path, _ in _found(check.text) if path in real}
        lines.append("found:")
        lines += [quarantine_file(quarantine, deny, path, sig) if path in confirmed
                  else f"{path}: not moved, a second scan did not confirm it" for path, sig in found]
        if len(confirmed) < len(found):
            lines.append(f"Warning: a file name in {folder} may hide a line break to fake these lines. "
                         f"The real infected file is still there: check that folder by hand.")
    if infected > len(found):
        lines.append(f"{infected - len(found)} found file(s) have a name that the scan output cannot show "
                     f"(see the clamscan output); they were not moved")
    if not found and not infected:
        lines.append("nothing found")
    return "\n".join(lines)


def _log(log, folder, result):
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M')} scan of {folder}\n{result}\n")
    except OSError:
        pass  # a full disk must not stop her from saying the result


def _records(quarantine):
    try:
        return json.loads((quarantine / RECORDS).read_text())
    except (OSError, json.JSONDecodeError):
        return []


def _save_records(quarantine, records):
    tmp = quarantine / (RECORDS + ".new")  # write, then replace: a crash never leaves half a file
    tmp.write_text(json.dumps(records, indent=1))
    tmp.replace(quarantine / RECORDS)


def _quarantined(quarantine):
    """All files in the quarantine folder, also ones without a record."""
    q = Path(quarantine)
    return [f for f in q.iterdir() if f.name not in (RECORDS, RECORDS + ".new")] if q.is_dir() else []


def quarantine_file(quarantine, deny, path, signature):
    """Move one found file into the quarantine, read only. Returns one line for the user."""
    if Path(path).is_symlink():  # safe_path follows links: never move the file that a link points to
        return f"{path} ({signature}): not moved, it is a link"
    try:
        real = safe_path(path, deny)
    except PathRefused as e:
        return f"{path} ({signature}): not moved, {e}"
    if not real.is_file():
        return f"{path} ({signature}): not moved, it is not a plain file"
    quarantine.mkdir(parents=True, exist_ok=True)
    quarantine.chmod(0o700)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}-{real.name}"
    mode = real.stat().st_mode & 0o777
    try:
        shutil.move(real, quarantine / name)
    except OSError as e:
        return f"{path} ({signature}): not moved, {e}"
    (quarantine / name).chmod(0o400)  # no write, no run
    _save_records(quarantine, [*_records(quarantine),
        {"name": name, "from": str(real), "signature": signature, "mode": mode, "date": time.strftime("%Y-%m-%d %H:%M")}])
    return f"{path} ({signature}): moved to the quarantine"


def list_quarantine(quarantine):
    records = _records(Path(quarantine))
    rows = [f"{r['name']}: {r['signature']}, from {r['from']}, {r['date']}" for r in records]
    known = {r["name"] for r in records}
    rows += [f"{f.name}: no record" for f in _quarantined(quarantine) if f.name not in known]
    if not rows:
        return Result(True, "the quarantine is empty", final=True)
    return Result(True, "\n".join(rows), untrusted=True)


def _find(quarantine, name):
    return [r for r in _records(Path(quarantine)) if name and (name == r["name"] or name in r["from"])]


def preview_restore(quarantine, name):
    hits = _find(quarantine, name)
    if len(hits) != 1:
        return False, f"{len(hits)} quarantined files match '{name}'. Use a name from list_quarantine."
    r = hits[0]
    return True, f"put {r['from']} back? ClamAV found {r['signature']} in it. Only say yes if you trust this file."


def restore_from_quarantine(quarantine, deny, name):
    quarantine = Path(quarantine)
    hits = _find(quarantine, name)
    if len(hits) != 1:
        return Result(False, f"{len(hits)} quarantined files match '{name}'", final=True)
    r = hits[0]
    target = Path(r["from"])
    try:
        safe_path(target.parent, deny)
    except PathRefused as e:
        return Result(False, f"refused: {e}", final=True)
    if target.exists() or target.is_symlink():
        return Result(False, f"failed: {target} exists again. Rename or move it first.", final=True)
    shutil.move(quarantine / r["name"], target)
    target.chmod(r["mode"])
    _save_records(quarantine, [x for x in _records(quarantine) if x["name"] != r["name"]])
    return Result(True, f"put back {target}")


def preview_empty(quarantine):
    n = len(_quarantined(quarantine))
    if not n:
        return False, "the quarantine is empty"
    return True, f"delete the {n} quarantined file(s) for good? This cannot be undone."


def empty_quarantine(quarantine):
    files = _quarantined(quarantine)
    for f in files:
        if f.is_dir() and not f.is_symlink():
            shutil.rmtree(f)
        else:
            f.unlink(missing_ok=True)
    if files:
        _save_records(Path(quarantine), [])
    return Result(True, f"deleted {len(files)} quarantined file(s)")


def stop_virus_scan(runner):
    if not scan["running"]:
        return Result(False, "no virus scan is running", final=True)
    runner.run(["pkill", "-x", "clamscan"])
    return Result(True, "stopped the virus scan")


def time_now():
    return Result(True, time.strftime("%A %d %B %Y, %H:%M"))
