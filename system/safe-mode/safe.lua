-- Hyprland SAFE MODE. A minimal config that does not depend on ~/dotfiles/desktop/hypr,
-- the hyprbars plugin, the bars, or Companion. Installed to /usr/local/share/hyprland-safe/.
-- Use it from the login screen ("Hyprland (safe mode)") when the normal session fails.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.config({
    general = { gaps_in = 4, gaps_out = 8, border_size = 2, layout = "dwindle",
                col = { active_border = "rgba(c9a15bff)", inactive_border = "rgba(303455aa)" } },
    decoration = { rounding = 8 },
    animations = { enabled = false },
    misc = { force_default_wallpaper = 0, disable_hyprland_logo = true, background_color = "rgba(1a1013ff)" },
    input = { kb_layout = "us", follow_mouse = 1 },
})

hl.on("hyprland.start", function()
    hl.exec_cmd("kitty --title 'SAFE MODE' sh -c 'echo SAFE MODE: the normal desktop is off.; "
        .. "echo Read ~/dotfiles/docs/RECOVERY.md for help.; echo; exec zsh'")
end)

local function power_menu()
    return "printf 'Log out\\nRestart\\nShut down\\n' | rofi -dmenu -p Power | "
        .. "while read c; do case $c in 'Log out') hyprctl dispatch 'hl.dsp.exit()';; "
        .. "Restart) systemctl reboot;; 'Shut down') systemctl poweroff;; esac; done"
end

hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))
hl.bind("SUPER + B", hl.dsp.exec_cmd("flatpak run com.google.Chrome"))
hl.bind("SUPER + Space", hl.dsp.exec_cmd("rofi -show drun"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + X", hl.dsp.exec_cmd(power_menu()))
hl.bind("SUPER + SHIFT + M", hl.dsp.exec_cmd("hyprctl dispatch 'hl.dsp.exit()'"))
hl.bind("SUPER + left", hl.dsp.focus({ direction = "left" }))
hl.bind("SUPER + right", hl.dsp.focus({ direction = "right" }))
for i = 1, 4 do
    hl.bind("SUPER + " .. i, hl.dsp.focus({ workspace = i }))
end
