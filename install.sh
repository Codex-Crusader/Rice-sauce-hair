#!/bin/sh
# Link the configs into your home folder. Read docs/INSTALL.md first.
# - Does not install packages and does not change /etc (see docs/INSTALL.md for those steps).
# - A file or folder that is in the way is moved to ~/.config-backup-<date>/, not deleted.
# - Safe to run again.
set -eu

REPO="$HOME/dotfiles"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ "$HERE" != "$REPO" ]; then
    echo "Clone the repo to $REPO first. Many configs use that path. Now: $HERE" >&2
    exit 1
fi

BACKUP="$HOME/.config-backup-$(date +%Y%m%d-%H%M%S)"

# link <file in repo> <target in home>
link() {
    src="$REPO/$1"
    dst="$2"
    mkdir -p "$(dirname "$dst")"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        return  # already linked
    fi
    if [ -e "$dst" ] || [ -L "$dst" ]; then
        mkdir -p "$BACKUP"
        mv "$dst" "$BACKUP/"
        echo "saved old $dst in $BACKUP/"
    fi
    ln -s "$src" "$dst"
    echo "linked $dst"
}

# Shell
link shell/zshrc        "$HOME/.zshrc"
link shell/zshenv       "$HOME/.zshenv"
link shell/zprofile     "$HOME/.zprofile"
link shell/bash_profile "$HOME/.bash_profile"

# Apps (whole folders)
for dir in hypr waybar kitty rofi swaync nwg-drawer pcmanfm-qt qt6ct fastfetch; do
    link "$dir" "$HOME/.config/$dir"
done
link gtk/gtk-3.0.css    "$HOME/.config/gtk-3.0/gtk.css"
link gtk/settings.ini   "$HOME/.config/gtk-3.0/settings.ini"
link gtk/gtk-4.0.css    "$HOME/.config/gtk-4.0/gtk.css"

# Desktop parts as user services (started by Hyprland through hypr-desktop.target)
for unit in "$REPO"/systemd/user/*.service "$REPO"/systemd/user/*.target "$REPO"/systemd/user/*.d; do
    name="$(basename "$unit")"
    link "systemd/user/$name" "$HOME/.config/systemd/user/$name"
done

# Scripts, fonts, file manager actions
link bin/health          "$HOME/.local/bin/health"
link bin/sysupdate       "$HOME/.local/bin/sysupdate"
link fonts/cinzel        "$HOME/.local/share/fonts/cinzel"
link file-manager-actions "$HOME/.local/share/file-manager/actions"

# Qt needs an absolute path to its color file
sed -i "s|@HOME@|$HOME|g" "$REPO/qt6ct/qt6ct.conf"

# Companion: your persona and the placeholder faces (only when you have none yet)
[ -f "$REPO/companion/persona.toml" ] || cp "$REPO/companion/persona.example.toml" "$REPO/companion/persona.toml"
AVATAR="$HOME/.local/share/castorice/avatar"
if [ ! -d "$AVATAR" ] || [ -z "$(ls -A "$AVATAR")" ]; then
    mkdir -p "$AVATAR"
    cp "$REPO"/assets/placeholders/avatar/*.png "$AVATAR/"
    echo "placeholder faces in $AVATAR (replace them, see docs/CUSTOMIZE.md)"
fi

# Folder for your card artwork
mkdir -p "$HOME/Pictures/chrysos-cards"

command -v systemctl >/dev/null && systemctl --user daemon-reload || true
fc-cache -f >/dev/null 2>&1 || true

echo
echo "Done. Next steps: docs/INSTALL.md, from step 4."
