-- Made by bin/theme-build from theme/palette.sh. Do not edit: change the palette, then run theme-build.
local c = {
    bg           = "0d0608",
    surface_low  = "120a0d",
    surface      = "1a1013",
    overlay      = "2a1c20",
    overlay_high = "3a2a30",
    ash          = "4e414f",
    marble       = "ede6da",
    marble_dim   = "d8cfc2",
    muted        = "bf9795",
    disabled     = "7a6a6a",
    parchment    = "e3c9a0",
    gold         = "c9a15b",
    gold_light   = "e0c084",
    terracotta   = "d66a2a",
    aegean       = "303455",
    aegean_light = "5b6fa8",
    aegean_pale  = "8094c9",
    wine         = "6b2d4a",
    wine_light   = "8f4a6b",
    wine_pale    = "b56d8f",
    lavender     = "c8a8eb",
    red          = "c0503a",
    red_light    = "e07a62",
    olive        = "8a9a5b",
    olive_light  = "a9b878",
    sea          = "5e9a9e",
    sea_light    = "86bdc0",
}

-- rgba(c.gold, "cc") -> "rgba(c9a15bcc)" for Hyprland. alpha: 2 hex digits (default ff).
function c.rgba(hex, alpha)
    return "rgba(" .. hex .. (alpha or "ff") .. ")"
end

return c
