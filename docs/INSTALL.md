# Install guide

Back to the [README](../README.md).

Read [Known issues](KNOWN-ISSUES.md) before you start. Do the steps in this order.

## 1. Requirements

- Arch Linux (or a distribution based on Arch).
- Hyprland 0.56 or newer, with the **Lua config** (`hyprland.lua`). Older Hyprland versions do not work.
- About 8 GB of free RAM or VRAM for the AI companion (optional).
- The repo must be in `~/dotfiles`. Many configs use this path.

## 2. Install the packages

Do a full update together with the install. Do not do partial updates on Arch.

```sh
sudo pacman -Syu --needed \
  hyprland hyprlock hypridle hyprsunset hyprpolkitagent xdg-desktop-portal-hyprland \
  waybar kitty rofi rofi-emoji swaync swayosd nwg-drawer pcmanfm-qt qt6ct mission-center \
  adw-gtk-theme papirus-icon-theme noto-fonts noto-fonts-emoji ttf-jetbrains-mono-nerd \
  zsh zsh-autosuggestions zsh-syntax-highlighting fzf fd less \
  cliphist wl-clipboard grim slurp satty playerctl brightnessctl \
  pipewire wireplumber pavucontrol networkmanager network-manager-applet blueman bluez udiskie \
  power-profiles-daemon gtk4-layer-shell python-gobject python-websockets \
  fastfetch imagemagick flatpak git cmake meson cpio pkgconf gcc
```

For the AI companion (optional):

```sh
sudo pacman -Syu --needed ollama clamav arch-audit pacman-contrib
# NVIDIA GPU: use ollama-cuda instead of ollama. AMD GPU: ollama-rocm.
```

The browser is Google Chrome from Flatpak. The keys and the companion start it with `flatpak run com.google.Chrome`:

```sh
flatpak install flathub com.google.Chrome
```

Optional: `carapace-bin` (from the AUR) gives better Tab completion. The shell works without it.

## 3. Clone and link

```sh
git clone --recurse-submodules https://github.com/Codex-Crusader/Rice-sauce-hair ~/dotfiles
~/dotfiles/install.sh
chsh -s /usr/bin/zsh
```

`install.sh` links the configs into `~/.config` and your home folder. It moves files that are in the way
to `~/.config-backup-<date>/`. It does not delete files. It also:

- makes `companion/persona.toml` from `persona.example.toml`,
- puts the placeholder faces in `~/.local/share/castorice/avatar/`,
- makes the card folder `~/Pictures/chrysos-cards/`.

## 4. Title bars (hyprbars plugin)

```sh
hyprpm update
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprbars
```

After each Hyprland update, run `hyprpm update` (or `sysupdate`, which does it for you), then log out and in.

## 5. The AI companion (optional)

1. Start Ollama and download the model:
   ```sh
   sudo systemctl enable --now ollama
   ollama pull qwen3:8b
   ```
2. Edit `~/dotfiles/companion/persona.toml`: her name, your name, and her character.
   See [The companion](COMPANION.md).
3. Chrome tab control (optional):
   ```sh
   ~/dotfiles/companion/setup.sh
   mkdir -p ~/.local/share/flatpak/overrides
   cp ~/dotfiles/flatpak/com.google.Chrome.override ~/.local/share/flatpak/overrides/com.google.Chrome
   ```
   Then in Chrome: open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**,
   and select `~/dotfiles/companion/chrome-extension`.
4. Hand-off to Claude Code (optional): install the `claude` command line tool. Without it, the companion
   cannot hand big tasks over, and it tells you so.

## 6. First start

Log in on a text console and type `Hyprland`. The desktop parts start as user services
(`hypr-desktop.target`). Press **Super+F1** for all keys.

If something is missing: press **Super+Shift+R** (restart the desktop parts), then run `health` in Kitty.

## 7. Optional system parts

These change files in `/etc` or `/boot`. Read each file before you copy it. You need sudo.

### Graphical login (greetd and ReGreet)

```sh
sudo pacman -Syu --needed greetd greetd-regreet cage
sudo cp ~/dotfiles/system/etc/greetd/* /etc/greetd/
sudo systemctl enable greetd
```

Test it once before you trust it. If the login screen loops, see [Recovery](RECOVERY.md).

### Safe mode session

A plain Hyprland session without plugins, bars, or the companion. Select it on the login screen.

```sh
sudo install -Dm644 ~/dotfiles/system/safe-mode/safe.lua /usr/local/share/hyprland-safe/safe.lua
sudo install -Dm644 ~/dotfiles/system/safe-mode/hyprland-safe.desktop /usr/share/wayland-sessions/hyprland-safe.desktop
```

### GRUB theme

```sh
sudo cp -r ~/dotfiles/grub/amphora /boot/grub/themes/
# In /etc/default/grub: GRUB_THEME="/boot/grub/themes/amphora/theme.txt"
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

The background is black. To use an image: `~/dotfiles/bin/grub-background <image>`.

### Hybrid GPU laptops (AMD or Intel iGPU plus NVIDIA)

Hyprland can run on the iGPU only, so the NVIDIA GPU can sleep.

1. Find the PCI address of the iGPU: `lspci -D | grep VGA`.
2. Put that address in `system/etc/udev/rules.d/61-gpu-names.rules`, then copy the file to
   `/etc/udev/rules.d/` and reboot. Check that `/dev/dri/amd-igpu` exists.
3. `shell/profile-gpu.sh` then sets `AQ_DRM_DEVICES` by itself for text logins.
4. For greetd: remove the `#` from the `WLR_DRM_DEVICES` line in `/etc/greetd/config.toml`
   and from the `[env]` lines in `/etc/greetd/regreet.toml`.
5. Start an app on the NVIDIA GPU with `prime-run <app>`.

### Snapshots, memory guard, and others

`system/etc/` also has the configs for snapper with snap-pac and grub-btrfs (`mkinitcpio.conf`), systemd-oomd,
Bluetooth, reflector, and pacman. They are examples from the author's machine. Compare them with your files.
Do not copy them blindly.
