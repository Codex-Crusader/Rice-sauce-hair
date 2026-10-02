"""Castorice, the desktop companion. Start with ~/dotfiles/companion/castorice (sets LD_PRELOAD).

Signals: SIGUSR1 focuses her text box (Super+A), SIGUSR2 hides or shows her (Super+Shift+A).
"""
import os
import random
import signal
import subprocess
import time
import tomllib
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GLibUnix", "2.0")
from gi.repository import GLib, GLibUnix, Gtk  # noqa: E402

from brain import Brain  # noqa: E402
from chrome_bridge import ChromeBridge  # noqa: E402
from ui import CompanionWindow  # noqa: E402

HERE = Path(__file__).parent
# The launcher preloads gtk4-layer-shell for this process only. Apps she starts must not get it:
# GTK 3 apps (Firefox) crash when GTK 4 is loaded into them.
os.environ.pop("LD_PRELOAD", None)


def on_main(fn):
    """Run fn on the GTK main loop (the brain calls back from a worker thread)."""
    return lambda *a: GLib.idle_add(lambda: fn(*a) and False)


class Companion(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.ricesaucehair.castorice")
        self.persona = tomllib.loads((HERE / "persona.toml").read_text())
        self.last_user_activity = time.time()
        self.battery = None  # (percent, status) from the last check
        self.remarks_paused = False

    def do_activate(self):
        if self.get_windows():  # already running
            return
        self.window = CompanionWindow(self, self.persona, self.send, self.confirm, self.menu)
        self.brain = Brain(self.persona, ChromeBridge(),
                           on_reply=on_main(lambda e, t: self.window.say(e, t)),
                           on_state=on_main(self.window.set_expression),
                           on_confirm=on_main(lambda q: self.window.say("worried", q, ask=True)))
        self.window.present()
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._signal(self.window.summon))
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self._signal(self.window.toggle_visible))
        GLib.timeout_add_seconds(3, self._greet)
        GLib.timeout_add_seconds(60, self._watch_battery)
        self._plan_idle_remark()

    def send(self, text):
        self.last_user_activity = time.time()
        self.brain.ask(text)

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
        elif name == "restart":
            subprocess.Popen(["systemctl", "--user", "restart", "castorice"])
        elif name == "log":
            subprocess.Popen(["kitty", "--title", "Castorice log", "less", "+G", str(Path.home() / ".cache/castorice/brain.log")])

    def confirm(self, yes):
        self.last_user_activity = time.time()
        self.brain.confirm(yes)

    @staticmethod
    def _signal(action):
        def handler():
            action()
            return True  # keep the signal handler
        return handler

    # ----- lifelike events -----

    def _greet(self):
        self.brain.remark(f"{self.persona['user']} just logged in. {self.brain.mood.away_text()} "
                          f"Greet them for this time of day, and let the time apart show if it was long.")
        return False

    def _plan_idle_remark(self):
        minutes = self.persona.get("idle_remark_minutes", 0)
        if minutes:
            GLib.timeout_add_seconds(int(minutes * 60 * random.uniform(0.7, 1.3)), self._idle_remark)

    def _idle_remark(self):
        if time.time() - self.last_user_activity > 600 and self.window.get_visible() and not self.remarks_paused:
            self.brain.remark("A quiet moment. Say something small: a thought, a gentle check-in, "
                              "or a memory. Do not ask for a task.")
        self._plan_idle_remark()
        return False

    def _watch_battery(self):
        bat = next(Path("/sys/class/power_supply").glob("BAT*"), None)
        if bat:
            percent = int((bat / "capacity").read_text())
            status = (bat / "status").read_text().strip()
            if self.battery:
                old_percent, old_status = self.battery
                if status != old_status and "Charging" in (status, old_status):
                    self.brain.remark(f"The charger was {'plugged in' if status == 'Charging' else 'unplugged'} "
                                      f"({percent}% battery).")
                elif status == "Discharging" and old_percent > 20 >= percent:
                    self.brain.remark(f"The battery is low: {percent}%. Worry a little, suggest the charger.")
            self.battery = (percent, status)
        return True


if __name__ == "__main__":
    Companion().run()
