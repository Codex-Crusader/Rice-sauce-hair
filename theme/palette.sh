# shellcheck shell=sh disable=SC2034  # sourced by other scripts: the names are used there
# Theme palette "Amphora". Taken from a red-figure Greek vase.
# The one source of all theme colors. After a change, run: theme-build
# (it writes the palette files for GTK, rofi, Hyprland, hyprlock, kitty, Qt and GRUB).
# Names: lower case in the apps (GOLD here is @gold in CSS, c.gold in Lua).

# Base
BG=0D0608           # black glaze (image)
SURFACE_LOW=120A0D  # sidebars: between BG and SURFACE
SURFACE=1A1013      # panels, bar background
OVERLAY=2A1C20      # hover, selected rows
OVERLAY_HIGH=3A2A30 # Qt mid tone
ASH=4E414F          # inactive buttons, bright black (image #4E414F)

# Text
MARBLE=EDE6DA       # main text: marble white
MARBLE_DIM=D8CFC2   # terminal white
MUTED=BF9795        # secondary text (image)
DISABLED=7A6A6A     # disabled text
PARCHMENT=E3C9A0    # the hint strip over the wallpaper

# Accents
GOLD=C9A15B         # antique gold: borders, accents (image #D28555 moved to gold)
GOLD_LIGHT=E0C084
TERRACOTTA=D66A2A   # vase figures (image)
AEGEAN=303455       # deep Aegean blue (image)
AEGEAN_LIGHT=5B6FA8 # blue that is readable on BG
AEGEAN_PALE=8094C9
WINE=6B2D4A         # wine purple (image #5C2411 and #4E414F moved to purple)
WINE_LIGHT=8F4A6B
WINE_PALE=B56D8F
LAVENDER=C8A8EB     # greeting on the desktop clock

# States, and the other terminal colors
RED=C0503A          # errors, urgent
RED_LIGHT=E07A62
OLIVE=8A9A5B        # green, kept in the palette
OLIVE_LIGHT=A9B878  # success
SEA=5E9A9E          # cyan
SEA_LIGHT=86BDC0
