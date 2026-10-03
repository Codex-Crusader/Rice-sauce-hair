#!/bin/sh
# One-time setup for Companion (no sudo needed).
# 1. Write the Chrome extension's copy of the secret token.
set -e
umask 077  # token.js is private from the start
cd "$(dirname "$(readlink -f "$0")")"
python3 -c 'import chrome_bridge; print("const COMPANION_TOKEN = \"%s\";" % chrome_bridge.load_token())' > chrome-extension/token.js
chmod 600 chrome-extension/token.js
echo "Token written. In Chrome: chrome://extensions > Developer mode > Load unpacked > $(pwd)/chrome-extension"
