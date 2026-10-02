# Recovery

Back to the [README](../README.md).

Start at the top: the first steps are the safest.

## The desktop looks wrong (no bar, no widgets, no companion)

1. Press **Super+Shift+R**. This restarts the bars, notifications, desktop icons, widgets, and the companion.
2. Open Kitty (**Super+Enter**) and run `health`. Each `WARN` line names a problem.
   (Some warnings are about the author's system, see [Known issues](KNOWN-ISSUES.md).)
3. See which part failed: `systemctl --user status hypr-desktop.target`, then
   `journalctl --user -u <part> -n 50` (for example `desk-widgets` or `castorice`).

## The title bars are gone

The title bar plugin must match the Hyprland version. Run `hyprpm update`, then log out and in.

## Hyprland does not start, or the login screen loops

1. If you installed the safe mode session: select **Hyprland (safe mode)** on the login screen.
   It does not use this config, the plugin, the bars, or the companion.
2. Check the normal config: `Hyprland --verify-config`.
3. If nothing works: press **Ctrl+Alt+F2**, log in as text, and run `sudo systemctl disable greetd`.
   Reboot. Log in on the text console and type `Hyprland`.
4. To undo this setup completely: remove the links that `install.sh` made, and move your old files back from
   `~/.config-backup-<date>/`.

## An update broke something

If you use snapper with snap-pac, every pacman run makes a snapshot before and after.

1. With grub-btrfs: reboot, open **Arch Linux snapshots** in GRUB, and boot the snapshot from before the update.
2. If the system works in the snapshot, the update caused the problem. Boot normally again and undo only
   that update: `sudo snapper -c root undochange <pre>..<post>` (the numbers from `sudo snapper -c root list`).

## The NVIDIA GPU is missing (hybrid laptops)

1. Shut down fully (not restart). Wait 10 seconds, then start again.
2. If it is still missing, check the firmware setup for a graphics mode setting, and set it to hybrid.

## The desktop froze

1. Wait 30 seconds. If you installed the systemd-oomd config, it stops the app that uses too much memory.
2. Press **Ctrl+Alt+F2**, log in, and run `top` to see what uses the memory.
3. Last step: hold the power button for 10 seconds.

## Useful commands

| Command | What it does |
|---|---|
| `health` | Checks the system. Each problem is one `WARN` line. |
| `sysupdate` | Updates pacman packages, the title bar plugin, and Flatpaks. |
| `journalctl -b -p err` | Errors since this boot. |
| `systemctl --user status hypr-desktop.target` | State of the desktop parts. |
