# Customize

Back to the [README](../README.md).

After a change, press **Super+Shift+R** to restart the desktop parts (bars, widgets, companion).
Hyprland reloads its own config when you save it.

## Wallpaper

The public version uses a black screen. To use an image, change it in each of these places:

| Where | File | Change |
|---|---|---|
| Desktop | `pcmanfm-qt/default/settings.conf` | `Wallpaper=/path/to/image.jpg` and `WallpaperMode=zoom` |
| Lock screen | `hypr/hyprlock.conf` | In `background`: replace the `color` line with `path = /path/to/image.jpg` |
| Login screen | `/etc/greetd/regreet.toml` | Remove the `#` from the `[background]` lines, set `path` (the image must be readable by the `greeter` user, for example in `/usr/share/backgrounds/`) |
| GRUB | `grub/amphora/background.png` | Run `~/dotfiles/bin/grub-background /path/to/image.jpg` |

You can also right-click the desktop, then **Desktop Preferences**.

## The companion's face (sprite sheet)

The companion shows one picture for each mood. The placeholder pictures are in
`~/.local/share/castorice/avatar/`. Replace them with your own:

| File | When it shows |
|---|---|
| `idle.png` | normal |
| `happy.png` | a task went well |
| `thinking.png` | while she works |
| `worried.png` | an error, or a risky request |

- Use PNG files with a transparent background, 170 x 170 pixels.
- To make her blink, add a closed-eye copy of each face: `idle-blink.png`, `happy-blink.png`, and so on.
  Each blink picture must have the same size and the same position as its open-eye picture,
  or she jumps when she blinks.
- The file names are set in `companion/persona.toml`, in `[expressions]`.

To cut a sheet with 4 faces (2 x 2) into separate files, with a white background made transparent:

```sh
magick sheet.png -crop 2x2@ +repage -alpha set -fuzz 8% -fill none \
  -draw "color 2,2 floodfill" -trim +repage -resize 170x170 \
  -background none -gravity center -extent 170x170 face-%d.png
```

Then rename `face-0.png` to `face-3.png` to the mood names. Check each result.

## Chrysos Heir cards (artwork)

Put your card images in `~/Pictures/chrysos-cards/`. Until you do, the widget shows "artwork here".

- PNG files. The file name is the caption: `castorice.png` shows **CASTORICE**. Use `-` for spaces.
- Tall cards look best: a width-to-height ratio of about 0.57 (for example 455 x 786).
- The desktop widget shows a random card and changes it every 5 minutes. Click it for the next card.
- Each new terminal window shows a random card next to the system information (fastfetch).
- `bin/soften-cards` makes a copy of each card in `~/.cache/chrysos-cards/` with see-through white parts.
  It runs when the widgets start. To change how see-through they are, edit the numbers in that script,
  then delete `~/.cache/chrysos-cards/` and restart the widgets.

## Colors

The palette is in `theme/palette.sh`. Change a color there first. Then change the same value in the files
that use it: `waybar/*.css`, `widgets/style.css`, `gtk/colors.css` (and `gtk/gtk-3.0.css`, `gtk/gtk-4.0.css`),
`swaync/style.css`, `rofi/`, `kitty/`, `qt6ct/colors/`, `hypr/hyprland.lua` (borders), `companion/ui.py` (bubble).

## Keys

All keys are in `hypr/keymap.lua`. Each key has a description. The descriptions also make the
hint strip above the taskbar and the cheat sheet (**Super+F1**).

- `hint = true` puts a key in the hint strip.
- **Super+H** hides or shows the hint strip.

## Desktop widgets

The widgets are in `widgets/desk.py` (one class for each widget) and `widgets/style.css`.

| To change | Where |
|---|---|
| Position of a widget | `layer_window(...)`: the edges and the margins in pixels |
| Remove a widget | `self.parts = [...]` at the end of the file: remove it from the list |
| Number or speed of the leaves | `Leaves`: `COUNT`, `FPS`, and `fall` in `new_leaf` |
| Time between cards | `Heirs.MINUTES` |
| Name in the greeting | `user` in `companion/persona.toml` |

The leaves move only when no window is open on the workspace, and not in the power-saver profile.

## Terminal greeting

`fastfetch/config.jsonc` sets the information lines. `shell/zshrc` (at the end) picks the card.
To turn the greeting off, remove that part of `shell/zshrc`.
