#!/usr/bin/env bash
# Run as the logged-in graphical user, in an X11 desktop session.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f kiosk.env ]]; then
  echo 'Copy scripts/kiosk.env.example to kiosk.env and edit it first.' >&2
  exit 1
fi
# Local operator-controlled configuration file; never populate it from uploads.
source kiosk.env
MONITOR_COUNT=${MONITOR_COUNT:-1}
SCREEN_WIDTH=${SCREEN_WIDTH:-1920}
SCREEN_HEIGHT=${SCREEN_HEIGHT:-1080}
if [[ "$MONITOR_COUNT" != 1 && "$MONITOR_COUNT" != 2 ]]; then
  echo 'MONITOR_COUNT must be 1 or 2.' >&2
  exit 1
fi
: "${CALENDAR_URL:?}" "${LEFT_OUTPUT:?}" "${LEFT_TOUCH:?}"
if [[ "$MONITOR_COUNT" == 2 ]]; then
  : "${RIGHT_OUTPUT:?Set RIGHT_OUTPUT for two monitors}" "${RIGHT_TOUCH:?Set RIGHT_TOUCH for two monitors}"
fi
if [[ "${XDG_SESSION_TYPE:-x11}" != x11 ]]; then
  echo 'This launcher requires X11. Select an X11 session; see docs/waterworks-calendar.md.' >&2
  exit 1
fi
CHROME=$(command -v chromium || command -v chromium-browser || true)
if [[ -z "$CHROME" ]]; then echo 'Install Chromium first.' >&2; exit 1; fi
if [[ "$MONITOR_COUNT" == 2 ]]; then
  xrandr --output "$LEFT_OUTPUT" --mode "${SCREEN_WIDTH}x${SCREEN_HEIGHT}" --primary --pos 0x0 --output "$RIGHT_OUTPUT" --mode "${SCREEN_WIDTH}x${SCREEN_HEIGHT}" --pos "${SCREEN_WIDTH}x0"
else
  xrandr --output "$LEFT_OUTPUT" --mode "${SCREEN_WIDTH}x${SCREEN_HEIGHT}" --primary --pos 0x0
fi
xinput map-to-output "$LEFT_TOUCH" "$LEFT_OUTPUT"
if [[ "$MONITOR_COUNT" == 2 ]]; then
  xinput map-to-output "$RIGHT_TOUCH" "$RIGHT_OUTPUT"
fi
xset s off
xset -dpms
runtime_dir="${XDG_CACHE_HOME:-$HOME/.cache}/waterworks-calendar"
mkdir -p "$runtime_dir"
trap 'kill $(jobs -pr) 2>/dev/null || true' EXIT INT TERM
launch() {
  local screen="$1" x="$2"
  while true; do
    "$CHROME" --user-data-dir="$runtime_dir/$screen" --no-first-run --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required --kiosk --window-position="$x,0" --window-size="${SCREEN_WIDTH},${SCREEN_HEIGHT}" "${CALENDAR_URL%/}/?screen=$screen&touch=1" || true
    sleep 3
  done
}
launch left 0 &
if [[ "$MONITOR_COUNT" == 2 ]]; then
  launch right "$SCREEN_WIDTH" &
fi
python3 scripts/display-power.py &
wait
