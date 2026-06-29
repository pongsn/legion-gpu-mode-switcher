#!/usr/bin/env bash
set -euo pipefail

POLICY_FILE="com.lenovolegion.gpumodetray.policy"
POLICY_DST="/usr/share/polkit-1/actions/$POLICY_FILE"
APP_DST="/usr/local/bin/legion-gpu-mode-switcher"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE="legion-gpu-mode-switcher.desktop"

echo "Installing polkit policy -> $POLICY_DST"
sudo install -m 644 "$POLICY_FILE" "$POLICY_DST"

echo "Installing app -> $APP_DST"
sudo install -m 755 main.py "$APP_DST"

echo "Installing autostart entry -> $AUTOSTART_DIR/$DESKTOP_FILE"
mkdir -p "$AUTOSTART_DIR"
install -m 644 "$DESKTOP_FILE" "$AUTOSTART_DIR/$DESKTOP_FILE"

echo "Done. Run now with: legion-gpu-mode-switcher"
echo "Will autostart on next login."
