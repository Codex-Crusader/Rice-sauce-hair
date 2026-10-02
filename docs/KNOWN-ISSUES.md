# Known issues

Back to the [README](../README.md).

This setup is glitchy. It was made for one laptop (Arch Linux, AMD iGPU with an NVIDIA RTX GPU, 1920 x 1080)
and tested only there. These are the problems that are known. There are more.

## General

- **The repo must be in `~/dotfiles`.** Many configs and services use that path.
- **Hyprland 0.56 or newer with the Lua config only.** Tools that send the old `hyprctl dispatch` syntax do not work.
  This is why the start menu runs nwg-drawer without its Hyprland mode, and the workspace number is a custom script.
- **The title bar plugin (hyprbars) breaks after each Hyprland update** until you run `hyprpm update`
  and log in again.
- **The layout assumes 1920 x 1080 at scale 1.** Widget positions are fixed pixel margins.
  On other screens they can overlap.
- **Chrome is the Flatpak version.** Keys and the companion run `flatpak run com.google.Chrome`.
  A different browser needs code changes.
- **`health` and `sysupdate` assume the author's system** (snapper, GRUB, an NVIDIA GPU, a git repo with a remote).
  On other systems they show warnings that are not real problems.
- **The system files in `system/` come from one machine.** Read them before you copy them.

## The companion

- **A small local model makes mistakes.** She can pick the wrong tool, misunderstand a request,
  or say that something is done when it failed. The code catches many of these cases, but not all.
- **She is slow without a GPU.** On a CPU, one answer can take 10 to 30 seconds.
- **She sometimes says "one moment" first.** The code then makes her act, so each task takes a little longer.
- **She cannot see apps that crash after they start.** She reports "opened" when the start worked.
- **The Chrome tab tools need the extension** (see the install guide). Without it, she can only open new tabs.
- **The hand-off needs the `claude` command line tool.** She can type into Claude windows that she opened,
  but not into other windows.
- **Her saved chat can confuse her.** If she keeps repeating a wrong answer, delete
  `~/.local/share/castorice/state.json` and restart her.

## The desktop

- **Minimized windows come back through a trick.** Hyprland does not focus a minimized window when you click it
  in the taskbar. It only marks the window "urgent". The config restores an urgent minimized window only when
  the mouse pointer is near the bottom of the screen. If your taskbar is not at the bottom, this does not work.
- **The falling leaves use about 5% of one CPU core** while the desktop is empty. They stop when a window
  is open on the workspace and in the power-saver profile.
- **The terminal card size assumes Kitty's default font size.** With another font size, the card can look stretched.
  Change `--logo-width` and `--logo-height` at the end of `shell/zshrc`.
- **The music widget shows album art only when the player gives a local file.** Otherwise it shows a placeholder.
- **The GPU status in the widget only knows NVIDIA.** On other systems it shows "missing".
