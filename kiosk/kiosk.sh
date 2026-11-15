#!/usr/bin/env bash
# Starts the wall screen(s) full-screen and keeps them running. Launched automatically at login.
set -u
CONF="$HOME/.config/opsboard"
# shellcheck disable=SC1091
source "$CONF/kiosk.env"
MODE="${MODE:-left}"; TOKEN="${TOKEN:-}"; HARDWARE_SLEEP="${HARDWARE_SLEEP:-1}"
SWAP_SCREENS="${SWAP_SCREENS:-0}"; SWAP_TOUCH="${SWAP_TOUCH:-0}"; TOUCH_MATCH="${TOUCH_MATCH:-touch}"
LOG="$CONF/kiosk.log"
exec >>"$LOG" 2>&1
echo "---- $(date) starting, mode=$MODE"

BROWSER="$(command -v chromium || command -v chromium-browser || true)"
if [[ -z "$BROWSER" ]]; then echo "Chromium is not installed"; exit 1; fi
WAYLAND=0; [[ -n "${WAYLAND_DISPLAY:-}" ]] && WAYLAND=1

url() { echo "$SERVER/display?screen=$1${TOKEN:+&token=$TOKEN}"; }

launch() {  # launch <left|right> <x-position>
  # A separate profile per screen lets two copies run side by side.
  local profile="$CONF/chromium-$1"
  mkdir -p "$profile"
  # Stop Chromium offering to "restore pages" after a power cut.
  sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' \
    "$profile/Default/Preferences" 2>/dev/null || true
  "$BROWSER" --user-data-dir="$profile" --kiosk --app="$(url "$1")" --window-position="$2,0" \
    --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble \
    --disable-features=Translate,TranslateUI --autoplay-policy=no-user-gesture-required \
    --overscroll-history-navigation=0 --disable-pinch --password-store=basic \
    --check-for-update-interval=31536000 &
}

echo "Waiting for the server at $SERVER"
until curl -fsS --max-time 5 "$SERVER/healthz" >/dev/null; do sleep 3; done

if [[ $WAYLAND -eq 0 ]]; then
  xset s off; xset s noblank; xset dpms 0 0 0          # never blank on a timer; we decide when
  command -v unclutter >/dev/null && unclutter -idle 0.5 -root &
fi

if [[ "$MODE" == "both" ]]; then
  if [[ $WAYLAND -eq 1 ]]; then
    echo "MODE=both needs the X11 desktop (sudo raspi-config > Advanced Options > Wayland > X11). Starting anyway."
  fi
  # Connected monitors, left to right:  "<x-offset> <name>"
  mapfile -t MONITORS < <(xrandr --listmonitors | awk 'NR>1 { split($3, g, "+"); print g[2], $NF }' | sort -n)
  if [[ ${#MONITORS[@]} -lt 2 ]]; then echo "Only ${#MONITORS[@]} monitor found; is the second cable plugged in?"; fi
  read -r X_LEFT OUT_LEFT <<<"${MONITORS[0]:-0 none}"
  read -r X_RIGHT OUT_RIGHT <<<"${MONITORS[1]:-1920 none}"
  if [[ "$SWAP_SCREENS" == 1 ]]; then
    launch right "$X_LEFT"; sleep 2; launch left "$X_RIGHT"
  else
    launch left "$X_LEFT"; sleep 2; launch right "$X_RIGHT"
  fi
  # Tie each touch panel to its own monitor, otherwise a touch is stretched across both.
  mapfile -t TOUCH < <(xinput list | grep -i "$TOUCH_MATCH" | grep -i pointer | sed -n 's/.*id=\([0-9]*\).*/\1/p')
  echo "Touch panels found: ${TOUCH[*]:-none}  monitors: $OUT_LEFT $OUT_RIGHT"
  if [[ ${#TOUCH[@]} -ge 2 ]]; then
    if [[ "$SWAP_TOUCH" == 1 ]]; then TOUCH=("${TOUCH[1]}" "${TOUCH[0]}"); fi
    xinput map-to-output "${TOUCH[0]}" "$OUT_LEFT"
    xinput map-to-output "${TOUCH[1]}" "$OUT_RIGHT"
  fi
else
  launch "$MODE" 0
fi

# Switch the monitors off outside work hours and back on when the server says so
# (work hours begin, or someone taps the screen).
LAST=""
while sleep 15; do
  [[ "$HARDWARE_SLEEP" == 1 ]] || continue
  STATE="$(curl -fsS --max-time 5 "$SERVER/api/state${TOKEN:+?token=$TOKEN}" || true)"
  [[ -n "$STATE" ]] || continue                       # server unreachable: leave the screens alone
  if [[ "$STATE" == *'"dark":true'* ]]; then NOW=off; else NOW=on; fi
  # Re-send "off" every time: on X11 a stray touch wakes the panel, and this puts it back to sleep
  # unless the touch landed on the page (which asks the server to wake up).
  if [[ "$NOW" == off || "$NOW" != "$LAST" ]]; then
    if [[ $WAYLAND -eq 1 ]]; then wlopm "--$NOW" '*' 2>/dev/null || true
    else xset dpms force "$NOW"; fi
  fi
  LAST="$NOW"
done
