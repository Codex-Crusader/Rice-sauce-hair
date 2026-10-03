-- Hyprland config. Theme "Amphora": colors from ~/dotfiles/theme/palette.sh.

------------------
---- COLORS ------
------------------
local c = {
    gold       = "c9a15b",
    terracotta = "d66a2a",
    aegean     = "303455",
    wine       = "6b2d4a",
    bg         = "0d0608",
}

-- Return an rgba() string for Hyprland. alpha is a 2-digit hex string.
local function rgba(hex, alpha)
    return "rgba(" .. hex .. (alpha or "ff") .. ")"
end

------------------
---- MONITORS ----
------------------
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = "auto",
})

-------------------
---- AUTOSTART ----
-------------------
local BIN    = os.getenv("HOME") .. "/dotfiles/bin/"

hl.on("hyprland.start", function()
    -- Export the session variables to systemd first, then start the supervised parts
    -- (taskbar, hint strip, notifications, desktop icons, Companion, idle, polkit).
    -- They restart on failure. Units: ~/dotfiles/system/systemd-user/
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP "
        .. "HYPRLAND_INSTANCE_SIGNATURE QT_QPA_PLATFORMTHEME && systemctl --user restart hypr-desktop.target")
    hl.exec_cmd("hyprpm reload -n")                -- load plugins (hyprbars); notifies on failure
    -- Tray apps, clipboard history, night light, and audio-follow-usb are user services
    -- under hypr-desktop.target (systemd/user/), so they restart on failure.
    hl.exec_cmd("sleep 20 && " .. BIN .. "health --notify") -- check once after login; notifies only on problems
end)

-- Stop the supervised parts when Hyprland exits, so they do not restart without a display.
hl.on("hyprland.shutdown", function()
    hl.exec_cmd("systemctl --user stop hypr-desktop.target")
end)

-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------
-- AQ_DRM_DEVICES is set in ~/.zprofile, before Hyprland starts.
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct") -- Qt apps (pcmanfm-qt) use the Amphora colors

-----------------------
---- LOOK AND FEEL ----
-----------------------
hl.config({
    general = {
        gaps_in  = 5,
        gaps_out = 12,

        -- Thin gold border on the active window
        border_size = 1,
        col = {
            active_border   = { colors = { rgba(c.gold), rgba(c.terracotta, "cc") }, angle = 45 },
            inactive_border = rgba(c.aegean, "aa"),
        },

        resize_on_border = true,
        allow_tearing    = false,
        layout           = "dwindle",
    },

    decoration = {
        rounding       = 12,
        rounding_power = 2,

        active_opacity   = 1.0,
        inactive_opacity = 0.95,

        shadow = {
            enabled      = true,
            range        = 12,
            render_power = 3,
            color        = 0xaa0d0608,
        },

        -- Soft blur behind translucent windows and the bar
        blur = {
            enabled  = true,
            size     = 6,
            passes   = 2,
            vibrancy = 0.17,
        },
    },

    animations = {
        enabled = true,
    },
})

-- Smooth animations: slow ease-out curves, a soft spring for windows
hl.curve("easeOutQuint", { type = "bezier", points = { {0.23, 1},   {0.32, 1} } })
hl.curve("linear",       { type = "bezier", points = { {0, 0},      {1, 1} } })
hl.curve("almostLinear", { type = "bezier", points = { {0.5, 0.5},  {0.75, 1} } })
hl.curve("quick",        { type = "bezier", points = { {0.15, 0},   {0.1, 1} } })
hl.curve("soft",         { type = "spring", mass = 1, stiffness = 200, dampening = 24 })

hl.animation({ leaf = "global",        enabled = true, speed = 10,  bezier = "default" })
hl.animation({ leaf = "border",        enabled = true, speed = 6,   bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true, speed = 5,   spring = "soft" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 4.5, spring = "soft",       style = "popin 90%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 1.8, bezier = "linear",     style = "popin 90%" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 2,   bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 1.6, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3,   bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true, speed = 4,   bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 4,   bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 1.5, bezier = "linear",       style = "fade" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 3,   bezier = "easeOutQuint", style = "slidefade 20%" })

hl.config({ dwindle = { preserve_split = true } })
hl.config({ master  = { new_status = "master" } })

----------------
----  MISC  ----
----------------
hl.config({
    misc = {
        force_default_wallpaper = 0,    -- pcmanfm-qt draws the wallpaper (black by default)
        disable_hyprland_logo   = true,
        background_color        = rgba(c.bg),
    },
})

---------------
---- INPUT ----
---------------
hl.config({
    input = {
        kb_layout    = "us",
        follow_mouse   = 1,
        natural_scroll = false,      -- mouse wheel: no natural scrolling
        sensitivity    = 0,          -- no change to the pointer speed
        accel_profile  = "adaptive", -- like "Enhance pointer precision" in Windows
        touchpad = {
            natural_scroll = true,   -- touchpad: content follows the fingers, as in Windows
        },
    },
})

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

-------------------------------------
---- WINDOW BEHAVIOUR AND KEYBINDS ----
-------------------------------------
require("windows")    -- tiling by default (Super+T: floating), snap, minimize, Alt+Tab (defines Desk)
require("keymap")     -- all keybinds; the one source for the cheat sheet
require("titlebars")  -- hyprbars title bars

--------------------------------
---- WINDOWS AND WORKSPACES ----
--------------------------------
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = { class = "^$", title = "^$", xwayland = true, float = true, fullscreen = false, pin = false },
    no_focus = true,
})

-- The cheat sheet window: floating, centered
hl.window_rule({ name = "cheatsheet", match = { class = "^cheatsheet$" }, float = true, size = "900 760", center = true })

-- Blur behind the bar, the launcher, and notifications
hl.layer_rule({ name = "blur-waybar",  match = { namespace = "^waybar$" },        blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-rofi",    match = { namespace = "^rofi$" },          blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-swaync",  match = { namespace = "^swaync" },        blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-drawer",  match = { namespace = "^nwg-drawer$" },    blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-desk",     match = { namespace = "^desk-card$" },    blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-companion", match = { namespace = "^companion$" },   blur = true, ignore_alpha = 0.3 })
