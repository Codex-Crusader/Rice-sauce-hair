"""Desktop widgets, theme "Amphora". Start with ~/dotfiles/desktop/widgets/desk (sets LD_PRELOAD).

Cards on the desktop layer: clock, system rings, music, art cards.
Golden leaves fall over the wallpaper; clicks go through them.
"""
import json
import math
import os
import random
import re
import subprocess
import time
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlparse

import getpass
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as Layer  # noqa: E402

os.environ.pop("LD_PRELOAD", None)  # apps started from here must not get gtk4-layer-shell

HERE = Path(__file__).parent
CARDS = Path.home() / "Pictures/art-cards"
SOFT_CARDS = Path.home() / ".cache/art-cards"  # see-through copies, made by bin/soften-cards
def user_name():
    """The name the widgets greet: "user" in companion/persona.toml, or the login name."""
    try:
        return tomllib.loads((HERE.parents[1] / "companion/persona.toml").read_text()).get("user") or getpass.getuser().title()
    except (OSError, tomllib.TOMLDecodeError):
        return getpass.getuser().title()


USER = user_name()


def read_palette():
    """{name: (r, g, b)} with values 0 to 1, from theme/palette.sh (the one source of theme colors)."""
    text = (HERE.parents[1] / "theme/palette.sh").read_text()
    return {name.lower(): tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
            for name, value in re.findall(r"^([A-Z_]+)=([0-9A-Fa-f]{6})\b", text, re.M)}


PALETTE = read_palette()
GOLD, LAVENDER, MARBLE, RED = PALETTE["gold"], PALETTE["lavender"], PALETTE["marble"], PALETTE["red"]
E = Layer.Edge


def layer_window(app, namespace, anchors, margins, layer=Layer.Layer.BOTTOM):
    """A window on the desktop layer, anchored to screen edges. No keyboard."""
    win = Gtk.Window(application=app)
    win.add_css_class("desk")
    Layer.init_for_window(win)
    Layer.set_namespace(win, namespace)
    Layer.set_layer(win, layer)
    Layer.set_keyboard_mode(win, Layer.KeyboardMode.NONE)
    for edge in anchors:
        Layer.set_anchor(win, edge, True)
    for edge, px in margins.items():
        Layer.set_margin(win, edge, px)
    return win


def label(text="", css=None, **kw):
    w = Gtk.Label(label=text, xalign=0, **kw)
    if css:
        w.add_css_class(css)
    return w


def read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


# ---------- clock ----------

class Clock:
    def __init__(self, app):
        self.win = layer_window(app, "desk-card", [E.TOP, E.LEFT], {E.TOP: 36, E.LEFT: 150})
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["card", "clock"])
        self.time = label(css="time")
        self.date = label(css="date")
        self.greet = label(css="greet")
        self.cycle = label(css="small")
        for w in (self.time, self.date, self.greet, self.cycle):
            box.append(w)
        self.win.set_child(box)
        self.win.present()
        self.tick()
        GLib.timeout_add_seconds(1, self.tick)

    def tick(self):
        now = time.localtime()
        self.time.set_text(time.strftime("%H:%M", now))
        self.date.set_text(time.strftime("%A, %-d %B", now))
        part = ("night" if now.tm_hour < 5 else "morning" if now.tm_hour < 12
                else "afternoon" if now.tm_hour < 17 else "evening" if now.tm_hour < 22 else "night")
        self.greet.set_text(f"Good {part}, {USER}" if part != "night" else f"Still awake, {USER}?")
        up = float(read("/proc/uptime", "0").split()[0])
        self.cycle.set_text(f"Day {now.tm_yday} of the Eternal Return  ·  awake {int(up // 3600)} h {int(up % 3600 // 60)} m")
        return True


# ---------- system rings ----------

# Only sysfs files here: nvidia-smi and lspci can wake a sleeping GPU, so do not call them.

def find_nvidia():
    """The sysfs folder of the NVIDIA GPU, or None. Searched one time, at start."""
    for dev in Path("/sys/bus/pci/devices").iterdir():
        if read(dev / "vendor") == "0x10de" and read(dev / "class").startswith("0x03"):
            return dev
    return None


def gpu_name(dev, ids=Path("/usr/share/hwdata/pci.ids")):
    """A short name from the PCI ID database: "AD107M [GeForce RTX 4060 Max-Q / Mobile]" -> "RTX 4060"."""
    device = read(dev / "device").removeprefix("0x")
    in_nvidia = False
    try:
        with ids.open(errors="ignore") as f:
            for line in f:
                if line.startswith("#") or not line.strip():  # comments are also inside a vendor section
                    continue
                if not line.startswith("\t"):
                    in_nvidia = line.startswith("10de ")
                elif in_nvidia and line.startswith(f"\t{device} "):
                    m = re.search(r"\b((?:RTX|GTX|MX|RTX A)\s?\d+\w*(?: Ti| SUPER)?)", line)
                    return m.group(1) if m else line.split(None, 1)[1].strip()
    except OSError:
        pass
    return "NVIDIA GPU"


NVIDIA = find_nvidia()
GPU_NAME = gpu_name(NVIDIA) if NVIDIA else "NVIDIA GPU"


def nvidia_state():
    """'awake' or 'asleep' from the PCI runtime power state."""
    if not NVIDIA:
        return "missing"
    return "awake" if read(NVIDIA / "power/runtime_status") == "active" else "asleep"


def cpu_temp():
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        if read(hw / "name") in ("k10temp", "coretemp", "zenpower"):
            return int(read(hw / "temp1_input", "0")) / 1000
    return int(read("/sys/class/thermal/thermal_zone0/temp", "0")) / 1000


class Rings:
    SIZE, GAP = 76, 14
    NAMES = ["CPU", "RAM", "DISK", "TEMP", "BAT"]

    def __init__(self, app):
        self.win = layer_window(app, "desk-card", [E.TOP, E.RIGHT], {E.TOP: 36, E.RIGHT: 40})
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["card"])
        box.append(label("VITALS", "heading"))
        self.area = Gtk.DrawingArea(content_width=5 * self.SIZE + 4 * self.GAP, content_height=self.SIZE + 18)
        self.area.set_draw_func(self.draw)
        box.append(self.area)
        self.gpu = label(css="small")
        box.append(self.gpu)
        self.win.set_child(box)
        self.values = [0] * 5
        self.texts = [""] * 5
        self.last_cpu = None
        self.win.present()
        self.update()
        GLib.timeout_add_seconds(2, self.update)

    def cpu(self):
        fields = [int(x) for x in read("/proc/stat").splitlines()[0].split()[1:]]
        idle, total = fields[3] + fields[4], sum(fields)
        used = 0.0
        if self.last_cpu:
            d_idle, d_total = idle - self.last_cpu[0], total - self.last_cpu[1]
            used = 1 - d_idle / d_total if d_total else 0
        self.last_cpu = (idle, total)
        return used

    def update(self):
        mem = dict(re.findall(r"(\w+):\s+(\d+)", read("/proc/meminfo")))
        ram = 1 - int(mem["MemAvailable"]) / int(mem["MemTotal"])
        st = os.statvfs("/")
        disk = 1 - st.f_bavail / st.f_blocks
        temp = cpu_temp()
        bat = next(Path("/sys/class/power_supply").glob("BAT*"), None)
        level = int(read(bat / "capacity", "0")) if bat else 0
        charging = bat and read(bat / "status") in ("Charging", "Full")
        cpu = self.cpu()
        self.values = [cpu, ram, disk, min(temp / 100, 1), level / 100]
        self.texts = [f"{cpu:.0%}", f"{ram:.0%}", f"{disk:.0%}", f"{temp:.0f}°", f"{level}%{'+' if charging else ''}"]
        self.gpu.set_text(f"{GPU_NAME}  ·  {nvidia_state()}      {int(mem['MemAvailable']) / 1048576:.1f} GiB free")
        self.area.queue_draw()
        return True

    def draw(self, _area, cr, _w, _h):
        r = self.SIZE / 2 - 6
        for i, (value, text, name) in enumerate(zip(self.values, self.texts, self.NAMES)):
            cx, cy = i * (self.SIZE + self.GAP) + self.SIZE / 2, self.SIZE / 2
            warn = (name == "TEMP" and value > 0.85) or (name == "BAT" and value < 0.2) or \
                   (name in ("RAM", "DISK") and value > 0.9)
            cr.set_line_width(5)
            cr.new_path()  # no line from the last text to this ring
            cr.set_source_rgba(*MARBLE, 0.12)
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.stroke()
            cr.set_source_rgba(*(RED if warn else GOLD), 0.95)
            cr.new_sub_path()
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(value, 0.01))
            cr.stroke()
            cr.select_font_face("JetBrainsMono Nerd Font")
            for txt, size, y, color, alpha in ((text, 14, cy + 5, MARBLE, 1), (name, 10, self.SIZE + 14, LAVENDER, 0.8)):
                cr.set_font_size(size)
                ext = cr.text_extents(txt)
                cr.set_source_rgba(*color, alpha)
                cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
                cr.show_text(txt)


# ---------- music ----------

def playerctl(*args):
    try:
        return subprocess.run(["playerctl", *args], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


class Music:
    FMT = "{{status}}\t{{title}}\t{{artist}}\t{{mpris:artUrl}}\t{{position}}\t{{mpris:length}}"

    def __init__(self, app):
        self.win = layer_window(app, "desk-card", [E.BOTTOM, E.LEFT], {E.BOTTOM: 40, E.LEFT: 150})
        row = Gtk.Box(spacing=14, css_classes=["card", "music"])
        self.art = Gtk.Image(pixel_size=84, css_classes=["art"])  # a fixed size, unlike Gtk.Picture
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        self.title = label(css="title", ellipsize=3, max_width_chars=30, width_chars=30)
        self.artist = label(css="small", ellipsize=3, max_width_chars=34)
        self.bar = Gtk.ProgressBar(css_classes=["progress"])
        buttons = Gtk.Box(spacing=6)
        self.play = None
        for icon, action, tip in (("󰒮", "previous", "Previous"), ("󰐊", "play-pause", "Play or pause"),
                                  ("󰒭", "next", "Next")):
            b = Gtk.Button(label=icon, css_classes=["ctl"], tooltip_text=tip)
            b.connect("clicked", lambda _b, a=action: (playerctl(a), GLib.timeout_add(300, self.update)))
            buttons.append(b)
            if action == "play-pause":
                self.play = b
        for w in (self.title, self.artist, self.bar, buttons):
            col.append(w)
        row.append(self.art)
        row.append(col)
        self.win.set_child(row)
        self.art_url = "unset"  # differs from every real value, so the first art always loads
        self.win.present()
        self.update()
        GLib.timeout_add_seconds(1, self.update)

    def update(self):
        out = playerctl("metadata", "--format", self.FMT)
        parts = out.split("\t") if out else []
        if len(parts) < 6 or not parts[1]:
            self.title.set_text("Silence, for now")
            self.artist.set_text("Play something, and it shows here")
            self.bar.set_fraction(0)
            self.set_art(None)
            self.play.set_label("󰐊")
            return True
        status, title, artist, art, pos, length = parts[:6]
        self.title.set_text(title)
        self.artist.set_text(artist or "unknown artist")
        self.bar.set_fraction(int(pos or 0) / int(length) if length.isdigit() and int(length) else 0)
        self.play.set_label("󰏤" if status == "Playing" else "󰐊")
        self.set_art(art)
        return True

    def set_art(self, url):
        if url == self.art_url:
            return
        self.art_url = url
        path = unquote(urlparse(url).path) if url and url.startswith("file://") else None
        if not (path and Path(path).exists()):
            path = str(Path.home() / ".local/share/companion/avatar/happy.png")
        self.art.set_from_file(path)


# ---------- art cards ----------

class Heirs:
    HEIGHT = 330
    MINUTES = 5

    def __init__(self, app):
        self.win = layer_window(app, "desk-card", [E.RIGHT], {E.RIGHT: 40})
        Layer.set_anchor(self.win, E.TOP, True)
        Layer.set_margin(self.win, E.TOP, 230)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["card", "heir"])
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=1200)
        self.name = label(css="heading")
        box.append(self.stack)
        box.append(self.name)
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.next())
        box.add_controller(click)
        box.set_tooltip_text("Art cards. Click for the next card.\nCards: ~/Pictures/art-cards")
        self.win.set_child(box)
        self.files, self.index, self.page = [], -1, 0
        self.win.present()
        self.next()
        GLib.timeout_add_seconds(self.MINUTES * 60, lambda: self.next() or True)
        # Make the see-through copies in the background: new cards take time, the widgets must not wait
        try:
            soften = subprocess.Popen([str(HERE.parents[1] / "bin/soften-cards")])
            GLib.child_watch_add(GLib.PRIORITY_DEFAULT, soften.pid, lambda *_: self.show_again())
        except OSError:
            pass

    def show_again(self):
        """The see-through copies are ready: show the current card again with its copy."""
        self.index -= 1
        self.next()

    def next(self):
        files = sorted(p for p in CARDS.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        if not files:
            self.name.set_text("Place card images in ~/Pictures/art-cards")
            return
        if files != self.files:
            self.files = files
            random.shuffle(self.files)
        self.index = (self.index + 1) % len(self.files)
        file = self.files[self.index]
        soft = SOFT_CARDS / (file.stem + ".png")  # copies are PNG (they need an alpha channel)
        file = soft if soft.exists() else file
        # Scale on load, so the card asks for HEIGHT px and not its full size
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(file), -1, self.HEIGHT)
        pic = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
        pic.set_can_shrink(False)  # exactly its own size: no stretching
        pic.set_halign(Gtk.Align.CENTER)
        old = self.stack.get_visible_child()  # before add: the first page added becomes visible at once
        self.page += 1
        self.stack.add_named(pic, str(self.page))
        self.stack.set_visible_child(pic)
        if old:  # remove the old page after the crossfade
            GLib.timeout_add(1500, lambda: self.stack.remove(old) or False)
        self.name.set_text(re.sub(r"[-_]+", " ", file.stem).strip().upper())  # same stem as the original


# ---------- golden leaves ----------

class Leaves:
    """Golden leaves fall over the wallpaper in an endless stream. Clicks go through them.
    A leaf that leaves the bottom starts again above the top edge, out of view, so the loop has no visible reset.
    They move only while the desktop is visible (no windows on the workspace) and not in power-saver mode.
    Each leaf is a small drawing that moves; a full-screen redraw would cost far more CPU."""
    COUNT, FPS, BOX = 16, 16, 64
    SHADES = [(0.95, 0.76, 0.33), (0.90, 0.66, 0.25), (0.98, 0.84, 0.45), (0.85, 0.56, 0.20)]

    def __init__(self, app):
        self.win = layer_window(app, "desk-leaves", [E.TOP, E.BOTTOM, E.LEFT, E.RIGHT], {})
        Layer.set_exclusive_zone(self.win, -1)  # cover the whole screen, also behind the bars
        self.area = Gtk.Fixed()
        # A Gtk.Fixed grows with its children, and a falling leaf would make the layer taller than the screen.
        # A view with EXTERNAL policy keeps the window at the screen size and cuts off what is outside.
        view = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                  vscrollbar_policy=Gtk.PolicyType.EXTERNAL, child=self.area)
        self.win.set_child(view)
        self.win.connect("realize", self.click_through)
        self.leaves, self.sprites = [], []
        for _ in range(self.COUNT):
            leaf = self.new_leaf(spread=True)
            sprite = Gtk.DrawingArea(content_width=self.BOX, content_height=self.BOX)
            sprite.set_draw_func(self.draw, leaf)
            self.area.put(sprite, -self.BOX, -self.BOX)
            self.leaves.append(leaf)
            self.sprites.append(sprite)
        self.saver = False    # power-saver profile: hide them
        self.covered = False  # windows on the workspace: keep them still
        self.last = time.monotonic()
        self.win.present()
        GLib.timeout_add(1000 // self.FPS, self.step)
        GLib.timeout_add_seconds(30, self.check_power)
        GLib.timeout_add_seconds(2, self.check_desktop)
        self.check_power()

    @staticmethod
    def click_through(win):
        import cairo
        win.get_surface().set_input_region(cairo.Region())

    def new_leaf(self, spread=False, leaf=None):
        """A leaf above the top edge. spread=True: anywhere on the screen height (at start, so no burst)."""
        leaf = leaf if leaf is not None else {}
        leaf.update({
            "x": random.uniform(0, 1),                              # base position, fraction of the width
            "y": random.uniform(-0.1, 1) if spread else random.uniform(-0.25, -0.05),  # fraction of the height
            "fall": random.uniform(0.035, 0.07),                    # screen heights per second
            "sway": random.uniform(20, 60),                         # px left and right
            "sway_speed": random.uniform(0.5, 1.1),                 # radians per second
            "spin": random.uniform(-1.2, 1.2),                      # radians per second
            "flip_speed": random.uniform(1.0, 2.4),                 # 3D tumble
            "t": random.uniform(0, 100),                            # own clock, so leaves are out of step
            "size": random.uniform(14, 24),
            "color": random.choice(self.SHADES),
            "alpha": random.uniform(0.8, 0.95),
        })
        return leaf

    def check_power(self):
        try:
            profile = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.TimeoutExpired):
            profile = ""
        self.saver = profile.strip() == "power-saver"
        for sprite in self.sprites:
            sprite.queue_draw()
        return True

    def check_desktop(self):
        try:
            out = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True, timeout=2).stdout
            self.covered = json.loads(out).get("windows", 0) > 0
        except (OSError, subprocess.TimeoutExpired, ValueError):
            self.covered = False
        return True

    def step(self):
        now = time.monotonic()
        dt = min(now - self.last, 0.1)  # real time, but no big jump after a pause
        self.last = now
        if self.saver or self.covered:
            return True
        w, h = self.win.get_width(), self.win.get_height()
        for leaf, sprite in zip(self.leaves, self.sprites):
            leaf["t"] += dt
            leaf["y"] += leaf["fall"] * dt
            if leaf["y"] > 1.05:  # out at the bottom: start again above the top, out of view
                self.new_leaf(leaf=leaf)
            x = leaf["x"] * w + leaf["sway"] * math.sin(leaf["t"] * leaf["sway_speed"])
            self.area.move(sprite, x - self.BOX / 2, leaf["y"] * h - self.BOX / 2)
            sprite.queue_draw()
        return True

    def draw(self, _area, cr, _w, _h, leaf):
        if self.saver:
            return
        t, s = leaf["t"], leaf["size"]
        cr.translate(self.BOX / 2, self.BOX / 2)
        # It tilts with the sway and turns slowly
        cr.rotate(leaf["spin"] * t + 0.5 * math.cos(t * leaf["sway_speed"]))
        cr.scale(max(abs(math.cos(t * leaf["flip_speed"])), 0.15), 1)  # 3D tumble: the leaf turns over
        r, g, b = leaf["color"]
        # Leaf blade: two curves from the stem to the tip
        cr.move_to(0, s)
        cr.curve_to(s * 0.75, s * 0.45, s * 0.6, -s * 0.55, 0, -s)
        cr.curve_to(-s * 0.6, -s * 0.55, -s * 0.75, s * 0.45, 0, s)
        cr.close_path()
        cr.set_source_rgba(r, g, b, leaf["alpha"])
        cr.fill_preserve()
        # A thin dark edge, so the leaf shows on the gold parts of the wallpaper
        cr.set_source_rgba(0.18, 0.09, 0.04, 0.7 * leaf["alpha"])
        cr.set_line_width(1.0)
        cr.stroke()
        # Midrib and stem, a darker gold, with a light line beside it
        cr.set_source_rgba(r * 0.55, g * 0.5, b * 0.4, leaf["alpha"])
        cr.set_line_width(1.3)
        cr.move_to(0, s * 1.35)
        cr.line_to(0, -s * 0.8)
        cr.stroke()
        cr.set_source_rgba(1, 0.95, 0.8, 0.45 * leaf["alpha"])
        cr.set_line_width(0.8)
        cr.move_to(s * 0.12, s * 0.7)
        cr.line_to(s * 0.12, -s * 0.6)
        cr.stroke()


# ---------- app ----------

class Desk(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.desk")

    def do_activate(self):
        if self.get_windows():
            return
        css = Gtk.CssProvider()
        css.load_from_path(str(HERE / "style.css"))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.parts = [Leaves(self), Clock(self), Rings(self), Music(self), Heirs(self)]  # leaves below the cards


if __name__ == "__main__":
    Desk().run()
