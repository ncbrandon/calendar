#!/usr/bin/env bash
# Installs the OpsBoard server on Debian 12/13 or Raspberry Pi OS (a Proxmox LXC, a VM, or a Pi).
# Run from the repository folder:   sudo bash deploy/install-server.sh
# Safe to run again to update: it keeps /etc/opsboard.env and your data.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo." >&2; exit 1; fi
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP=/opt/opsboard
DATA=/var/lib/opsboard
ENVFILE=/etc/opsboard.env

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq python3 python3-venv sqlite3 curl openssl

echo "==> Creating the opsboard user and folders"
id opsboard >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin opsboard
mkdir -p "$APP" "$DATA"
cp -r "$SRC/app" "$SRC/requirements.txt" "$APP/"
chown -R opsboard:opsboard "$APP" "$DATA"

echo "==> Installing Python packages"
[[ -d "$APP/.venv" ]] || sudo -u opsboard python3 -m venv "$APP/.venv"
sudo -u opsboard "$APP/.venv/bin/pip" install --quiet --upgrade pip
sudo -u opsboard "$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt"

if [[ ! -f "$ENVFILE" ]]; then
  echo "==> Writing $ENVFILE with a new password and screen token"
  PASSWORD="$(openssl rand -base64 12 | tr -d '/+=')"
  TOKEN="$(openssl rand -hex 24)"
  cat > "$ENVFILE" <<ENV
OPSBOARD_PASSWORD=$PASSWORD
OPSBOARD_KIOSK_TOKEN=$TOKEN
OPSBOARD_DATA=$DATA
# ANTHROPIC_API_KEY=
ENV
  chmod 600 "$ENVFILE"
  NEW_ENV=1
fi

echo "==> Installing the service"
cp "$SRC/deploy/opsboard.service" /etc/systemd/system/opsboard.service
systemctl daemon-reload
systemctl enable --now opsboard
systemctl restart opsboard
sleep 2
curl -fsS http://127.0.0.1:8080/healthz >/dev/null && echo "==> Server is running."

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Web page:      http://$IP:8080"
echo "Settings file: $ENVFILE   (password and screen token are in there:  sudo cat $ENVFILE)"
if [[ "${NEW_ENV:-0}" == 1 ]]; then
  echo "Password:      $PASSWORD"
  echo "Screen token:  $TOKEN"
  echo "Write both down now. You will need the token when you set up the wall screens."
fi
