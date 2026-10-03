#!/bin/sh
# Set up this desktop in your home folder. Read docs/INSTALL.md first.
#   sh install.sh           make the links, the Qt color setting, the example persona, the placeholder faces
#   sh install.sh --check   a dry run: show what would be linked, change nothing
#   sh install.sh --remove  remove the links again (your own files stay)
# It never moves or deletes your files: a file in the way is reported, and you decide.
# It does not install packages and does not change /etc or /boot (see docs/INSTALL.md for those steps).
# Safe to run again.
set -eu

REPO="$HOME/dotfiles"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ "$HERE" != "$REPO" ]; then
    echo "Clone the repo to $REPO first. Many configs use that path. Now: $HERE" >&2
    exit 1
fi

case "${1:-}" in
    --check)  exec bash "$REPO/bin/link" --check ;;
    --remove) exec bash "$REPO/bin/link" --remove ;;
    "") ;;
    *) echo "Usage: sh install.sh [--check | --remove]" >&2; exit 1 ;;
esac

if ! bash "$REPO/bin/link"; then
    echo
    echo "Some links were not made: see the SKIP lines. Move those files away, then run install.sh again."
fi

# Qt needs an absolute path to its colors. Written into ~/.config, so the repo stays clean.
mkdir -p "$HOME/.config/qt6ct"
[ -e "$HOME/.config/qt6ct/qt6ct.conf" ] || sed "s|@HOME@|$HOME|g" "$REPO/theme/qt6ct/qt6ct.conf" > "$HOME/.config/qt6ct/qt6ct.conf"

# Companion: your persona and the placeholder faces (only when you have none yet)
[ -f "$REPO/companion/persona.toml" ] || cp "$REPO/companion/persona.example.toml" "$REPO/companion/persona.toml"
AVATAR="$HOME/.local/share/companion/avatar"
if [ ! -d "$AVATAR" ] || [ -z "$(ls -A "$AVATAR")" ]; then
    mkdir -p "$AVATAR"
    cp "$REPO"/assets/placeholders/avatar/*.png "$AVATAR/"
    echo "placeholder faces in $AVATAR (replace them, see docs/CUSTOMIZE.md)"
fi

# Folder for your card artwork
mkdir -p "$HOME/Pictures/art-cards"

command -v systemctl >/dev/null && systemctl --user daemon-reload || true
fc-cache -f >/dev/null 2>&1 || true

echo
echo "Done. Next steps: docs/INSTALL.md, from step 4."
