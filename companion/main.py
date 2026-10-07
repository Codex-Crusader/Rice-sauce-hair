"""Companion, the desktop companion. Start with companion/companion (sets LD_PRELOAD).

Signals: SIGUSR1 focuses her text box (Super+A), SIGUSR2 hides or shows her (Super+Shift+A).
"""
import logging
import os
import random
import signal
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GLibUnix", "2.0")
from gi.repository import GLib, GLibUnix, Gtk

import config as config_mod
import context
import tools
from chrome_bridge import ChromeBridge
from session import Session
from ui import CompanionWindow

# The launcher preloads gtk4-layer-shell for this process only. Apps she starts must not get it:
# GTK 3 apps (Firefox) crash when GTK 4 is loaded into them.
os.environ.pop("LD_PRELOAD", None)


def setup_logging(config):
    """Log to the cache folder. Called once at start, not at import."""
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=config.log_file, level=logging.INFO, format="%(asctime)s %(message)s")


def on_main(fn):
    """Run fn on the GTK main loop (the brain calls back from a worker thread)."""
    return lambda *a: GLib.idle_add(lambda: fn(*a) and False)


class Companion(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.companion")
        self.config = config_mod.load()
        setup_logging(self.config)
        self.persona = self.config.persona
        self.last_user_activity = time.time()
        self.battery = None  # (percent, status) from the last check
        self.remarks_paused = False

    def do_activate(self):
        if self.get_windows():  # already running
            return
        self.window = CompanionWindow(self, self.config, self.send, self.confirm, self.menu)
        chrome = ChromeBridge(self.config.config_dir / "token")
        self.session = Session(self.config, chrome,
                               on_reply=on_main(lambda e, t: self.window.say(e, t)),
                               on_state=on_main(self.window.set_expression),
                               on_question=on_main(lambda q: self.window.say("worried", q, ask=True)))
        self.window.asking = self.session.asking
        tools.scan["on_done"] = lambda result: self.session.remark(
            f"The virus scan finished. Result (file names come from outside):\n{context.LABEL}\n{result}\n"
            f"Tell {self.persona['user']} the result plainly.", must_say=True)
        self.window.present()
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._signal(self.window.summon))
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self._signal(self.window.toggle_visible))
        GLib.timeout_add_seconds(3, self._greet)
        GLib.timeout_add_seconds(60, self._watch_battery)
        self._plan_idle_remark()

    def send(self, text):
        self.last_user_activity = time.time()
        self.session.send(text)

    def menu(self, name):
        """Right-click menu on her face."""
        if name == "health":
            self.send("Run a health check and tell me what you find.")
        elif name == "pause":
            self.remarks_paused = not self.remarks_paused
            self.window.say("idle", "I will stay quiet until you talk to me." if self.remarks_paused
                            else "I may speak up now and then again.")
        elif name == "hide":
            self.window.toggle_visible()
        elif name == "stop":
            self.session.cancel()
            self.window.say("idle", "I stopped.")
        elif name == "off":
            subprocess.Popen([str(self.config.bin("companion-switch")), "off"])
        elif name == "restart":
            subprocess.Popen(["systemctl", "--user", "restart", "companion"])
        elif name == "log":
            subprocess.Popen(["kitty", "--title", "Companion log", "less", "+G", str(self.config.log_file)])

    def confirm(self, yes):
        self.last_user_activity = time.time()
        self.session.answer(yes)

    @staticmethod
    def _signal(action):
        def handler():
            action()
            return True  # keep the signal handler
        return handler

    # ----- lifelike events -----

    def _greet(self):
        self.session.remark(f"{self.persona['user']} just logged in. {self.session.mood.away_text()} "
                          f"Greet them for this time of day, and let the time apart show if it was long.")
        return False

    def _plan_idle_remark(self):
        minutes = self.persona.get("idle_remark_minutes", 0)
        if minutes:
            GLib.timeout_add_seconds(int(minutes * 60 * random.uniform(0.7, 1.3)), self._idle_remark)

    def _idle_remark(self):
        if time.time() - self.last_user_activity > 600 and self.window.get_visible() and not self.remarks_paused:
            self.session.remark("A quiet moment. Say something small: a thought, a gentle check-in, "
                              "or a memory. Do not ask for a task.")
        self._plan_idle_remark()
        return False

    def _watch_battery(self):
        bat = next(Path("/sys/class/power_supply").glob("BAT*"), None)
        try:
            percent = int((bat / "capacity").read_text())
            status = (bat / "status").read_text().strip()
        except (TypeError, OSError, ValueError):  # no battery, or a bad read: try again next minute
            return True
        if self.battery:
            old_percent, old_status = self.battery
            # Only Discharging means "on battery". Charging, Full and "Not charging" all mean plugged in.
            if (status == "Discharging") != (old_status == "Discharging"):
                self.session.remark(f"The charger was {'unplugged' if status == 'Discharging' else 'plugged in'} "
                                  f"({percent}% battery).")
            elif status == "Discharging" and old_percent > 20 >= percent:
                self.session.remark(f"The battery is low: {percent}%. Worry a little, suggest the charger.")
        self.battery = (percent, status)
        return True


if __name__ == "__main__":
    Companion().run()
