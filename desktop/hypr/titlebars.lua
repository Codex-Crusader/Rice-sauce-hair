-- Title bars from the hyprbars plugin (built with hyprpm).
-- Buttons are added right to left: close, maximize, minimize.
-- Double-click the bar to maximize. Drag the bar to move the window.

-- The plugin loads after the first config pass. Skip until it is loaded.
if not (hl.plugin and hl.plugin.hyprbars) then return end

local c = require("palette")  -- made by bin/theme-build from theme/palette.sh

hl.config({
    plugin = {
        hyprbars = {
            bar_height                 = 28,
            bar_color                  = c.rgba(c.surface, "ee"),
            ["col.text"]               = c.rgba(c.marble),
            bar_text_font              = "Cinzel",
            bar_text_size              = 11,
            bar_text_weight            = "bold",
            bar_text_align             = "left",
            bar_buttons_alignment      = "right",
            bar_padding                = 12,
            bar_button_padding         = 8,
            bar_blur                   = true,
            bar_part_of_window         = true,
            bar_precedence_over_border = true,
            inactive_button_color      = c.rgba(c.ash),
            on_double_click            = "hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = \"maximized\" })'",
        },
    },
})

local function button(color, icon, action)
    hl.plugin.hyprbars.add_button({
        bg_color = color,
        fg_color = c.rgba(c.bg),
        size     = 14,
        icon     = icon,
        action   = action,
    })
end

button(c.rgba(c.red), "󰖭", "hyprctl dispatch 'hl.dsp.window.close()'")                               -- close
button(c.rgba(c.gold), "󰖯", "hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = \"maximized\" })'") -- maximize
button(c.rgba(c.aegean_light), "󰖰", "hyprctl dispatch Desk.minimize")                                -- minimize
