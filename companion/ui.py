"""The floating companion window: bubble on the left, her face, text box under her."""
import math
import random
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as LayerShell

AVATAR_SIZE = 170
KEYBOARD_SECONDS = 20  # Super+A with nothing typed: the keyboard goes back after this time

CSS_FILE = Path(__file__).with_name("ui.css")  # colors by name from theme/gtk/palette.css


def place_in_corner(window, right, bottom, keyboard):
    """Make window a layer surface in the bottom-right corner, above other windows."""
    LayerShell.init_for_window(window)
    LayerShell.set_namespace(window, "companion")
    LayerShell.set_layer(window, LayerShell.Layer.TOP)
    LayerShell.set_anchor(window, LayerShell.Edge.BOTTOM, True)
    LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)
    LayerShell.set_margin(window, LayerShell.Edge.BOTTOM, bottom)
    LayerShell.set_margin(window, LayerShell.Edge.RIGHT, right)
    LayerShell.set_keyboard_mode(window, keyboard)


class CompanionWindow(Gtk.ApplicationWindow):
    def __init__(self, app, config, on_send, on_confirm, on_menu):
        super().__init__(application=app)
        self.avatar_dir = config.avatar_dir
        self.persona = persona = config.persona
        self.on_send, self.on_confirm, self.on_menu = on_send, on_confirm, on_menu
        self.expressions = persona["expressions"]
        self.hide_timer = None
        self.asking = lambda: False  # main.py sets this to session.asking
        self.textures = {}
        self.expression = "idle"
        self.add_css_class("companion")
        self._layer_shell()
        self._build()
        self._load_css()
        self.phase = 0.0
        self.float_timer = None
        self.idle_keyboard_timer = None
        self._start_float()
        self.connect("notify::visible", lambda *_: self._start_float() if self.get_visible() else self._stop_float())
        self._plan_blink()

    # ----- setup -----

    def _layer_shell(self):
        place_in_corner(self, right=14, bottom=6, keyboard=LayerShell.KeyboardMode.ON_DEMAND)

    def _build(self):
        # Right-aligned: her face stays in the corner when the bubble is hidden
        # Speech bubble: its own window left of her face, so it leaves no empty space when hidden
        self.bubble_window = Gtk.Window(application=self.get_application())
        self.bubble_window.add_css_class("companion")
        place_in_corner(self.bubble_window, right=14 + AVATAR_SIZE + 6, bottom=6 + 60,
                        keyboard=LayerShell.KeyboardMode.NONE)
        self.bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.END)
        self.bubble.add_css_class("bubble")
        name = Gtk.Label(label=self.persona["name"].upper(), xalign=0)
        name.add_css_class("name")
        self.text = Gtk.Label(wrap=True, xalign=0, width_chars=24, max_width_chars=34)
        self.buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        yes, no = Gtk.Button(label="Yes"), Gtk.Button(label="No")
        yes.add_css_class("yes")
        yes.connect("clicked", lambda *_: self._answer(True))
        no.connect("clicked", lambda *_: self._answer(False))
        self.buttons.append(no)
        self.buttons.append(yes)
        for w in (name, self.text, self.buttons):
            self.bubble.append(w)
        self.bubble_window.set_child(self.bubble)
        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._cancel_hide())
        hover.connect("leave", lambda *_: self._schedule_hide(4))
        self.bubble.add_controller(hover)

        # Her face, and the text box under her
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.face = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.face.set_size_request(AVATAR_SIZE, AVATAR_SIZE)
        self.entry = Gtk.Entry(placeholder_text=f"Talk to {self.persona['name']}...", width_chars=18)
        self.entry.add_css_class("talk")
        self.entry.set_tooltip_text("Type here and press Enter (Super+A).\nEsc: stop typing.")
        self.face.set_tooltip_text(f"{self.persona['name']}\nClick: talk to her. Right-click: menu "
                                   "(health check, pause her remarks, hide, restart, log).\nSuper+Shift+A: hide or show.")
        self.entry.connect("activate", self._send)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, key, *_: key == Gdk.KEY_Escape and (self.release() or True))
        self.entry.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.entry.grab_focus())
        self.face.add_controller(click)
        self._menu()
        column.append(self.face)
        column.append(self.entry)

        self.set_child(column)
        self.set_expression("idle")

    def _menu(self):
        """Right-click on her face: a small menu."""
        items = [("Stop what she is doing", "stop"), ("Health check", "health"), ("Pause her remarks", "pause"), ("Hide (Super+Shift+A)", "hide"),
                 ("Restart her", "restart"), ("Open her log", "log"), ("Turn her off (companion-switch on)", "off")]
        menu = Gio.Menu()
        group = Gio.SimpleActionGroup()
        for label, name in items:
            menu.append(label, f"companion.{name}")
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, n=name: self.on_menu(n))
            group.add_action(action)
        self.insert_action_group("companion", group)
        self.popover = Gtk.PopoverMenu.new_from_model(menu)
        self.popover.set_parent(self.face)
        self.popover.set_has_arrow(False)
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self.popover.popup())
        self.face.add_controller(right)

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_FILE))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ----- behaviour -----

    def _start_float(self):
        if not self.float_timer:
            self.float_timer = GLib.timeout_add(100, self._float)  # 10 steps a second is smooth enough

    def _stop_float(self):
        """Hidden: no timer, so a hidden companion costs no CPU."""
        if self.float_timer:
            GLib.source_remove(self.float_timer)
            self.float_timer = None

    def _float(self):
        """A slow, gentle bob, so she looks alive."""
        self.phase += 0.16
        offset = round(4 * math.sin(self.phase))
        self.face.set_margin_top(4 + offset)
        self.face.set_margin_bottom(4 - offset)
        return True

    def _texture(self, file):
        """Load each image once, so a blink never flickers."""
        if file not in self.textures:
            self.textures[file] = Gdk.Texture.new_from_filename(str(file)) if file.exists() else None
        return self.textures[file]

    def set_expression(self, name):
        self.expression = name if name in self.expressions else "idle"
        texture = self._texture(self.avatar_dir / self.expressions[self.expression])
        if texture:
            self.face.set_paintable(texture)

    # ----- blinking: the same face with closed eyes (<name>-blink.png) for a moment -----

    def _plan_blink(self):
        GLib.timeout_add(random.randint(2500, 5500), self._blink)

    def _blink(self, again=True):
        file = self.avatar_dir / self.expressions[self.expression]
        closed = self._texture(file.with_name(file.stem + "-blink.png"))
        if closed:
            self.face.set_paintable(closed)
            GLib.timeout_add(140, self._open_eyes, again and random.random() < 0.2)
        else:
            self._plan_blink()
        return False

    def _open_eyes(self, double):
        self.set_expression(self.expression)  # the face she has now, in case it changed during the blink
        if double:
            GLib.timeout_add(180, self._blink, False)
        else:
            self._plan_blink()
        return False

    def say(self, expression, text, ask=False):
        self.set_expression(expression)
        self.text.set_text(text)
        self.buttons.set_visible(ask)
        self.bubble_window.set_default_size(1, 1)  # fit the new text
        self.bubble_window.present()
        if ask:
            self._cancel_hide()
        else:
            self._schedule_hide(6 + len(text) // 14)  # longer text stays longer

    def _send(self, entry):
        text = entry.get_text().strip()
        if not text:
            return
        entry.set_text("")
        self.release()
        self.on_send(text)  # the session decides if a typed "yes" or "no" answers a question

    def _answer(self, yes):
        self.buttons.set_visible(False)
        self.on_confirm(yes)

    def _schedule_hide(self, seconds):
        self._cancel_hide()
        self.hide_timer = GLib.timeout_add_seconds(seconds, self._hide_bubble)

    def _cancel_hide(self):
        if self.hide_timer:
            GLib.source_remove(self.hide_timer)
            self.hide_timer = None

    def _hide_bubble(self):
        self.hide_timer = None
        if not self.asking():  # the bubble stays while a question is open
            self.bubble_window.set_visible(False)
            self.set_expression("idle")
        return False

    def summon(self):
        """Super+A: take the keyboard so the user can type at once. Enter or Esc gives it back.
        With an empty text box, the keyboard also goes back after KEYBOARD_SECONDS."""
        self.set_visible(True)
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.EXCLUSIVE)
        self.entry.grab_focus()
        self._plan_keyboard_release()

    def _plan_keyboard_release(self):
        if self.idle_keyboard_timer:
            GLib.source_remove(self.idle_keyboard_timer)
        self.idle_keyboard_timer = GLib.timeout_add_seconds(KEYBOARD_SECONDS, self._release_if_idle)

    def _release_if_idle(self):
        self.idle_keyboard_timer = None
        if self.entry.get_text().strip():  # still typing: wait again
            self._plan_keyboard_release()
        else:
            self.release()
        return False

    def release(self):
        if self.idle_keyboard_timer:
            GLib.source_remove(self.idle_keyboard_timer)
            self.idle_keyboard_timer = None
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.ON_DEMAND)

    def toggle_visible(self):
        """Super+Shift+A: hide her, or show her again."""
        self.release()
        self.set_visible(not self.get_visible())
        if not self.get_visible():
            self.bubble_window.set_visible(False)
