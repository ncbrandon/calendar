#!/usr/bin/env bash
# Turns a Raspberry Pi (Raspberry Pi OS with desktop) or a Debian mini PC into an OpsBoard wall screen.
# Run as the normal desktop user, NOT with sudo:
#     bash kiosk/install-kiosk.sh http://192.168.1.50:8080 left  YOUR_SCREEN_TOKEN
#     bash kiosk/install-kiosk.sh http://192.168.1.50:8080 right YOUR_SCREEN_TOKEN
#     bash kiosk/install-kiosk.sh http://localhost:8080    both  YOUR_SCREEN_TOKEN
set -euo pipefail

SERVER="${1:?First argument: the server address, e.g. http://192.168.1.50:8080}"
MODE="${2:?Second argument: left, right, or both}"
TOKEN="${3:-}"
case "$MODE" in left|right|both) ;; *) echo "Mode must be left, right, or both" >&2; exit 1 ;; esac
if [[ $EUID -eq 0 ]]; then echo "Run this as the desktop user, without sudo." >&2; exit 1; fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$HOME/.config/opsboard"

echo "==> Installing packages (asks for your password)"
sudo apt-get update -qq
sudo apt-get install -y -qq curl fonts-noto-color-emoji x11-xserver-utils xinput unclutter wlopm || true
if ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null; then
  sudo apt-get install -y -qq chromium || sudo apt-get install -y -qq chromium-browser
fi

echo "==> Writing $CONF/kiosk.env"
mkdir -p "$CONF" "$HOME/.local/bin" "$HOME/.config/autostart"
sed -e "s|^SERVER=.*|SERVER=${SERVER%/}|" -e "s|^MODE=.*|MODE=$MODE|" -e "s|^TOKEN=.*|TOKEN=$TOKEN|" \
  "$HERE/kiosk.env.example" > "$CONF/kiosk.env"
chmod 600 "$CONF/kiosk.env"
install -m 755 "$HERE/kiosk.sh" "$HOME/.local/bin/opsboard-kiosk"

echo "==> Starting the screen automatically at login"
cat > "$HOME/.config/autostart/opsboard-kiosk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=OpsBoard wall screen
Exec=$HOME/.local/bin/opsboard-kiosk
X-GNOME-Autostart-enabled=true
DESKTOP

echo
echo "Done. Two things left to do by hand:"
echo "  1. sudo raspi-config  >  System Options  >  Boot / Auto Login  >  Desktop Autologin"
if [[ "$MODE" == "both" ]]; then
  echo "  2. sudo raspi-config  >  Advanced Options  >  Wayland  >  X11    (needed to drive two touch screens from one computer)"
else
  echo "  2. (nothing else for a one-screen computer)"
fi
echo "Then:  sudo reboot"
echo "Log file if something looks wrong:  $CONF/kiosk.log"
