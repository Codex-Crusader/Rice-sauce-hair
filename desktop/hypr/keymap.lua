-- Key map. This is the one source for all keybinds.
-- The hint strip and the cheat sheet read the descriptions with
-- "hyprctl binds -j" (see ~/dotfiles/bin/keyhints).
-- "hint = true" puts the bind in the hint strip above the taskbar.

local BIN = os.getenv("HOME") .. "/dotfiles/bin/"
local exec = hl.dsp.exec_cmd
local unpack = table.unpack or unpack
local call = function(fn, ...) local args = { ... } return function() fn(unpack(args)) end end

local terminal = "kitty"
local files    = "pcmanfm-qt"
local browser  = "flatpak run com.google.Chrome"
local repair   = "systemctl --user restart hypr-desktop.target && notify-send -a Desktop 'Desktop parts restarted'"

-- { keys, action, description, options }
local keymap = {
    -- Start menu and apps
    { "SUPER + Super_L",      exec(BIN .. "start-menu"),         "Start menu",              { release = true, hint = true } },
    { "SUPER + Return",       exec(terminal),                    "Terminal",                { hint = true } },
    { "SUPER + E",            exec(files),                       "File manager",            { hint = true } },
    { "SUPER + B",            exec(browser),                     "Chrome" },
    { "SUPER + Space",        exec("rofi -show drun"),           "App search (Rofi)" },
    { "SUPER + A",            exec("pkill -USR1 -f '^companion'"), "Talk to Companion (Esc to stop)" },
    { "SUPER + SHIFT + A",    exec("pkill -USR2 -f '^companion'"), "Hide or show Companion" },
    { "CTRL + SHIFT + Escape", exec("missioncenter"),            "Task manager" },

    -- Windows
    { "ALT + F4",             hl.dsp.window.close(),             "Close window",            { hint = true } },
    { "SUPER + Q",            hl.dsp.window.close(),             "Close window" },
    { "ALT + Tab",            call(Desk.cycle, true),            "Next window",             { hint = true } },
    { "ALT + SHIFT + Tab",    call(Desk.cycle, false),           "Previous window" },
    { "SUPER + left",         call(Desk.snap, "left"),           "Snap or move left",       { hint = true } },
    { "SUPER + right",        call(Desk.snap, "right"),          "Snap or move right" },
    { "SUPER + up",           Desk.maximize,                     "Maximize" },
    { "SUPER + down",         Desk.restore,                      "Restore" },
    { "SUPER + M",            Desk.minimize,                     "Minimize" },
    { "SUPER + F",            hl.dsp.window.fullscreen(),        "Fullscreen" },
    { "SUPER + T",            Desk.toggle_floating,              "Floating on or off for this workspace" },
    { "SUPER + P",            hl.dsp.window.pseudo(),            "Pseudo-tile (tiling mode)" },
    { "SUPER + J",            hl.dsp.layout("togglesplit"),      "Change split direction (tiling mode)" },

    -- System
    { "SUPER + L",            exec("pidof hyprlock || hyprlock"), "Lock screen",            { hint = true } },
    { "SUPER + V",            exec(BIN .. "clipboard"),          "Clipboard history" },
    { "SUPER + I",            exec("swaync-client -t -sw"),      "Notifications and quick settings" },
    { "SUPER + N",            exec("swaync-client -t -sw"),      "Notifications and quick settings" },
    { "SUPER + SHIFT + S",    exec(BIN .. "screenshot area"),    "Screenshot of an area" },
    { "Print",                exec(BIN .. "screenshot area"),    "Screenshot of an area" },
    { "SHIFT + Print",        exec(BIN .. "screenshot full"),    "Screenshot of the screen" },
    { "CTRL + Print",         exec(BIN .. "screenshot annotate"), "Screenshot of an area, then draw on it" },
    { "SUPER + period",       exec("rofi -modi emoji -show emoji"), "Emoji picker" },
    { "SUPER + H",            exec(BIN .. "toggle-hints"),       "Hide or show this hint strip" },
    { "SUPER + F1",           exec(BIN .. "cheatsheet"),         "Cheat sheet (all keys)",  { hint = true } },
    { "SUPER + X",            exec(BIN .. "power-menu"),         "Power menu" },
    { "SUPER + SHIFT + R",    exec(repair),                      "Repair: restart bars, notifications, Companion" },
    { "SUPER + SHIFT + M",    exec(BIN .. "power-menu"),         "Power menu (log out asks first)" },

    -- Scratchpad
    { "SUPER + S",            hl.dsp.workspace.toggle_special("magic"), "Show the scratchpad" },
    { "SUPER + grave",        hl.dsp.window.move({ workspace = "special:magic" }), "Move window to the scratchpad" },

    -- Mouse
    { "SUPER + mouse:272",    hl.dsp.window.drag(),              "Move window (Super + left drag)",  { mouse = true } },
    { "SUPER + mouse:273",    hl.dsp.window.resize(),            "Resize window (Super + right drag)", { mouse = true } },
    { "SUPER + mouse_down",   hl.dsp.focus({ workspace = "e+1" }), "Next workspace" },
    { "SUPER + mouse_up",     hl.dsp.focus({ workspace = "e-1" }), "Previous workspace" },
}

-- Workspaces 1 to 10
for i = 1, 10 do
    local key = i % 10 -- 10 maps to key 0
    table.insert(keymap, { "SUPER + " .. key, hl.dsp.focus({ workspace = i }), "Go to workspace " .. i })
    table.insert(keymap, { "SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }), "Move window to workspace " .. i })
end

-- Laptop keys. These also work on the lock screen.
local laptop_keys = {
    { "XF86AudioRaiseVolume",  "swayosd-client --output-volume raise", "Volume up",       true },
    { "XF86AudioLowerVolume",  "swayosd-client --output-volume lower",      "Volume down",     true },
    { "XF86AudioMute",         "swayosd-client --output-volume mute-toggle",     "Mute",            false },
    { "XF86AudioMicMute",      "swayosd-client --input-volume mute-toggle",   "Microphone mute", false },
    { "XF86MonBrightnessUp",   "swayosd-client --brightness raise",                  "Brightness up",   true },
    { "XF86MonBrightnessDown", "swayosd-client --brightness lower",                  "Brightness down", true },
    { "XF86AudioNext",         "playerctl next",                                 "Next track",      false },
    { "XF86AudioPause",        "playerctl play-pause",                           "Play or pause",   false },
    { "XF86AudioPlay",         "playerctl play-pause",                           "Play or pause",   false },
    { "XF86AudioPrev",         "playerctl previous",                             "Previous track",  false },
}
for _, k in ipairs(laptop_keys) do
    table.insert(keymap, { k[1], exec(k[2]), k[3], { locked = true, repeating = k[4] } })
end

-- Register all binds. The description goes to "hyprctl binds".
for _, entry in ipairs(keymap) do
    local keys, action, text, opts = entry[1], entry[2], entry[3], entry[4] or {}
    local bind_opts = { description = (opts.hint and "[hint] " or "") .. text }
    for k, v in pairs(opts) do
        if k ~= "hint" then bind_opts[k] = v end
    end
    hl.bind(keys, action, bind_opts)
end
