# Waterworks Calendar — equipment, installation, and operating guide

Version 1.0.0 · Updated November 14, 2026 · Project: ncbrandon/calendar

This repository contains a working self-hosted application, not just a mockup. It uses Python 3.12+, SQLite, and browser JavaScript. No paid API, build step, cloud database, or Python package installation is required. Docker is optional. The same application is intended for x86-64 and ARM64; ARM hardware and physical monitors still require installation testing.

## One touchscreen now, second screen later

Current purchasing decision (November 14, 2026): **one 32-inch touchscreen now**, with the option to add a second in 2027. Keep the Proxmox server plus one Raspberry Pi 5. A mini PC is optional.

Buy one monitor, one mount, one micro-HDMI-to-HDMI video cable, and one USB touch data cable now. The verified November 14 listing for the Beetronics 32TS7M was **$919 before sales tax**, with free shipping advertised. Pair prices below remain for expansion planning; they are not the current purchase quantity or a guarantee of next year's prices. The existing equipment table describes the eventual two-screen arrangement.

The first screen shows a full-size current month. Previous/next arrows open any other month; Today returns to the current month. Event editing, the on-screen keyboard, P-code sample reminders, weekly duty dropdowns, payroll markers, media, effects, and Markdown exports work in the existing single-month view.

For the first-screen kiosk, copy `scripts/kiosk.env.example` to `kiosk.env`, keep `MONITOR_COUNT=1`, and fill in only CALENDAR_URL, LEFT_OUTPUT, and LEFT_TOUCH. Leave RIGHT_OUTPUT and RIGHT_TOUCH commented out. Run `bash scripts/kiosk.sh`. It configures only the first output, maps only its touchscreen, and opens only `/?screen=left&touch=1`. Existing two-monitor installations must explicitly set `MONITOR_COUNT=2` before using this launcher update. Use `/?screen=left&touch=1` to open this view manually without the launcher; the central management page can still show both months.

When adding the second monitor:

1. Connect its video cable to the Pi's second micro-HDMI port and its touch USB cable to a free USB port.
2. Set `MONITOR_COUNT=2` in the same kiosk.env. Uncomment and fill in RIGHT_OUTPUT and RIGHT_TOUCH using actual names from xrandr/xinput. Keep both screens at the configured matching resolution.
3. Stop and restart the kiosk launcher (or reboot the configured display PC/Pi).
4. The first display shows the current month and the second shows the next month. Test each touchscreen's mapping and display power behavior.

No database migration, second server, new application instance, or re-entry of events/sample records is needed. Choose the Pi 5's power supply and cooling for the final two-screen use now; purchase the extra screen, mount, and cables when ready. Physical dual-screen operation still requires testing with the chosen hardware.

## Current U.S. touchscreen prices — checked November 14, 2026

Your selected arrangement can use the existing Proxmox server plus one Raspberry Pi 5 driving both displays. A mini PC is optional; it is not an additional requirement.

These are listed USD prices before sales tax, mounts, and any checkout shipping charges. Stock and prices can change. All options below are 32-inch-class touchscreens, exceeding the requested 28-inch minimum.

| Display / seller | Condition | Each | Two | Availability / installation notes |
| --- | --- | ---: | ---: | --- |
| [Beetronics 32TS7M, direct](https://www.beetronics.com/32-inch-touchscreen) | New | $919.00 | $1,838.00 | Listed in stock; manufacturer advertises free shipping and 30-day returns. Metal housing, 100 mm VESA, explicit Linux support, two-year warranty. |
| [ViewSonic TD3207, B&H](https://www.bhphotovideo.com/c/product/1798898-REG/viewsonic_td3207_32_open_frame_touch.html) | New | $1,029.99 | $2,059.98 | Listed in stock; free delivery advertised, confirm for your address. Open-frame design; mounting/edge protection needs planning. |
| [Greentouch 3202E, Tyco Touch](https://tycotouch.com/products/greentouch-3202e) | New | $1,080.00 | $2,160.00 | Base variant without optional PC or mount. Built to order, approximately four-week lead time, noncancelable; confirm Raspberry Pi/Linux touch support before considering. |
| [ViewSonic TD3207-S, manufacturer outlet](https://www.viewsonic.com/us/td3207-s.html) | Refurbished | $771.99 | $1,543.98 if two become available | Out of stock when checked. Refurbished warranty specifications list a 90-day repair warranty, rather than the new-product three-year warranty. |

Purchase preference for this project: **two Beetronics 32TS7M units**, because the listed new price is lower than the other verified new options above, Linux support is explicit, and a complete metal housing simplifies wall installation. Buy/test one first with the actual Pi, touch mapping, and sleep/wake behavior before purchasing the second. Manufacturer support does not replace an actual dual-screen installation test.

The [new ViewSonic direct listing](https://www.viewsonic.com/us/products/monitors/touch-screen-monitors/td3207.html) also shows $1,029.99 and a three-year limited warranty. Its Raspberry Pi/Linux touch behavior still needs confirmation. No current U.S. iiyama price was verified in this comparison, so earlier iiyama allowances remain planning estimates rather than purchase quotes.

Budget $1,838 for the Beetronics pair, plus the chosen mounts, cable lengths, and sales tax. Standard HDMI alone does not carry touch input; each screen also needs a USB data connection to the Pi. Avoid substituting inexpensive Android signage/tablet products without verifying external USB touch support.

## Recommended equipment

Use your existing Proxmox host for the application and a Raspberry Pi 5 at the screen(s). A mini PC is an alternative display computer. Proxmox does not connect to the touchscreens directly. The table below lists the eventual two-screen configuration; purchase one screen and its mounting/cables initially.

| Qty | Equipment | Specification / buying guidance | Planning allowance, USD |
| --- | --- | --- | ---: |
| 2 | 32-inch capacitive touchscreen | iiyama ProLite TF3215MC-B2AG or TF3215MC-B2; 1920×1080, HDMI/DP video and USB touch, Linux compatibility listed by manufacturer | $700–$1,800 each |
| 1 | Intel mini PC | N100/N150-class or better, 8–16 GB RAM, 128+ GB SSD, two independent HDMI/DP outputs, two USB ports for touch, wired Ethernet | $250–$600 |
| 2 | VESA mounts | Match exact monitor VESA pattern and weight; add framing/enclosure for open-frame displays | $100–$250 total |
| 2 each | Video and USB touch cables | HDMI/DP for video PLUS a separate USB data cable per monitor; verify supplied cables and required lengths | $40–$100 total |
| 1 | UPS | Sized for actual connected loads and desired runtime; server/network protection takes priority | $150–$350 |
| 1 | Keyboard / mouse | For commissioning and recovery | $25–$50 |

Approximate total: $1,965–$4,950, excluding Proxmox server, enclosure, tax, labor, and extra network equipment. These are allowances, not checked vendor quotes.

The manufacturer lists the iiyama models as 32-inch-class (31.5-inch viewable), Linux-compatible touch monitors. Both exceed the requested 28-inch minimum. They are open-frame commercial units: plan proper mounting and edge protection. Confirm touch with the actual Linux installation and any gloves before committing to both units. Plan roughly 56–60 inches of wall width plus clearance. Do not assume a front-face protection rating protects the whole installation from wet conditions.

Manufacturer references:

- [iiyama TF3215MC-B2AG](https://iiyama.com/ie_en/products/prolite-tf3215mc-b2ag/)
- [iiyama TF3215MC-B2](https://iiyama.com/gl_en/products/prolite-tf3215mc-b2/)
- [ViewSonic TD3207 alternative](https://www.viewsonic.com/us/products/monitors/touch-screen-monitors/td3207.html): 32-inch touch candidate; confirm exact Linux touch compatibility with vendor before substituting.

### Raspberry Pi alternative

A Pi 5 with 8 GB RAM, official 27 W USB-C supply, active cooling/case, 128+ GB SSD and appropriate interface, two micro-HDMI-to-HDMI cables, and Ethernet can host the application and drive both screens. Allow about $180–$300 for the complete Pi equipment rather than the mini PC. Prefer SSD storage over continuous writes to an SD card. The [Pi 5 manufacturer specifications](https://www.raspberrypi.com/products/raspberry-pi-5/) list dual 4K output; that does not establish performance for arbitrary videos and effects. Start at dual 1920×1080 and test the actual media. Use a supported 64-bit OS.

## What version 1.0 does

- Central management page, one-screen kiosk by default, and optional separate left/right touchscreen views.
- Current month on the left, next month on the right; paired arrows and Today.
- Shared month navigation, synchronized by polling every 10 seconds.
- Return to the current month after five minutes of historical browsing; reset at a new month in the facility timezone.
- Add/edit/delete events; optional weekly, monthly, or annual recurrence and multiday events.
- Touch keyboard, including in the sign-in and edit dialogs.
- Thursday–Wednesday Jody/Marcus duty rotation and Brandon day/week overrides.
- Optional federal holiday labels, independent payroll week markers, and custom holiday events.
- 59 draft well sampling requirements extracted at panel/individual-task level from the supplied Drinking Water Watch PDF.
- Review windows, estimated costs, planned/actual collection dates, progress stages, and next-period creation.
- Wednesday bottle-order tasks generated from planned collection dates.
- Cost-balanced monthly proposals within approved windows, with optional monthly budget ceiling. Proposals need an Apply action.
- On-calendar deadline and bottle reminders; no email or SMS delivery in this version.
- Document upload/storage; scheduled uploaded GIF/image/MP4/WebM playback in a floating panel, muted and looping.
- Seasonal leaves/snow, explicit rain/snow/leaves, or weather-driven effects with seasonal fallback.
- Work-hours black overlay and an X11 kiosk script for actual DPMS monitor sleep/wake.
- Date-range Markdown export, authenticated full backup download, and an internal audit log.
- Password login, PBKDF2 password hashing, HttpOnly/SameSite cookies, write CSRF tokens, and login throttling.

The initial release uses one shared administrator credential. It does not implement individual staff accounts, AI/OCR permit interpretation, automatic state website refresh, regulatory report submission, email/SMS, or offline writes. New permits can be uploaded and their verified requirements entered manually. Two editors changing the same record at once receive conflict protection; refresh after a conflict. A saved sample plan is an operational aid, not evidence that a required sample or report was completed.

## Your configured rules

- Facility timezone: America/New_York.
- Jody begins Thursday, November 12, 2026, ending Wednesday, November 18.
- Marcus begins Thursday, November 19, ending Wednesday, November 25.
- Alternate Jody and Marcus every Thursday after that, including across month/year boundaries.
- A Thursday dropdown defaults to assigning the entire Thursday–Wednesday duty week. Other days default to a single-day override; the edit panel allows either scope.
- Brandon coverage does not shift the underlying rotation. A day override takes priority over a week override.
- P-codes remain the display names. D01 and distribution-system monitoring are excluded from the initial seed.
- Bottle requests are on Wednesday of the Monday-based week BEFORE collection. Example: collection Tuesday, December 8, 2026 → request Wednesday, December 2, 2026. This rule also applies to Friday or Sunday collections in that same week.
- Next-week delivery has no guaranteed weekday. Confirm Received before collection, and move collection if needed while staying inside the approved window. Delivery is not automatically confirmed by elapsed time.
- Payroll is disabled until its actual start day and payday are configured. Screen hours provisionally default to Monday–Friday, 07:00–17:00; change them in Settings.

## Sampling import

Source: the user-supplied 16-page North Carolina Drinking Water Watch PDF, printed November 14, 2026. System NC0105010, Town of West Jefferson. The original PDF is not published in this repository. Upload a copy through Files & media if desired. The public project contains schedule-derived configuration, not live records, credentials, or uploaded files.

P-codes: P03, P04, P05, P07, P08, P10, P11, P12.

| Requirement | Frequency/window in the snapshot |
| --- | --- |
| Nitrate, all eight P-codes | Annual, 2026 current period |
| Inorganics / secondaries / VOC, P05 | Annual, 2026 current period |
| Inorganics / secondaries / VOC, other seven P-codes | Three-year, 2026–2028 |
| SOC, all eight P-codes | Three-year, 2026–2028 |
| P04 simazine and di(2-ethylhexyl) phthalate | Individual three-year records, 2026–2028 |
| P07 atrazine | Individual three-year record, 2026–2028 |
| Radiological panels, P04/P10/P11/P12 | Nine-year, 2026–2034 |
| Gross alpha / uranium / combined radium, P03/P05/P07 | Nine-year, 2026–2034 |
| Gross alpha / uranium, P08 | Nine-year, 2026–2034 |
| Combined radium, P08 | Six-year, 2026–2031 |

Each imported item starts unreviewed, with no collection date or assumed cost. “0 / unsatisfied” describes the snapshot, not a determination of noncompliance. Verify recent samples and pending laboratory records. Source page references are preserved per item. Panel-level tasks do not imply one bottle per group; reconcile individual exceptions and panel coverage before ordering or estimating costs. Operational/historical level entries from the last two PDF pages are not converted to well bottle tasks.

The planner only proposes dates for reviewed, open, unplanned requirements with an entered cost (zero explicitly allowed). It prefers weekdays at least two weeks ahead and aims to leave 90 days before the final deadline where feasible. It spreads estimated spending by calendar month, including existing planned costs. It is a transparent greedy allocator, not a guarantee of a globally optimal budget. Conflicts remain visible rather than moving deadlines. Seasonal/operational constraints beyond the entered collection window must be reviewed manually. A single narrow seasonal window can be represented by editing the start/end dates.

Stages: Verify records → Planned → Ordered → Received → Collected → Delivered → Results received → Reviewed → Complete; Resample needed is also available. Enter actual collection before advancing collection/result stages. Complete requires review plus an actual date; confirm accepted results and required reporting yourself. Open next monitoring period copies the cycle into a new unreviewed record while preserving the completed record and guarding against duplicate next periods. New periods are not silently assumed approved.

## Install on Proxmox — recommended

1. Create a Debian 13 or Ubuntu 24.04 LTS VM with 2 virtual CPUs, 4 GB RAM, 32+ GB SSD-backed disk, a normal LAN bridge, and a DHCP reservation/static address. Keep it separate from the Proxmox host OS. Install OS updates and enable time synchronization.
2. Install Docker Engine and the Compose plugin using the official instructions for [Debian](https://docs.docker.com/engine/install/debian/) or [Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Confirm `docker compose version`. Use `sudo docker` if your account is not authorized to use Docker.
3. Install `git` and `python3` from the OS package manager, then:

```bash
git clone https://github.com/ncbrandon/calendar.git waterworks-calendar
cd waterworks-calendar
python3 scripts/configure.py
# Privately open .env and save ADMIN_PASSWORD in your password manager.
docker compose up -d --build
docker compose ps
```

4. The default binds only to the VM itself at http://127.0.0.1:8080. For the recommended private online page, install [Tailscale](https://tailscale.com/download/linux) on this VM and every computer/phone/kiosk that needs access. Authenticate them to your tailnet. Then run on the VM:

```bash
sudo tailscale serve --bg http://127.0.0.1:8080
```

Use the HTTPS address Tailscale prints. It is a private online page, available to authorized tailnet devices, not a public website. After confirming HTTPS works, set `COOKIE_SECURE=1` in .env and recreate with `docker compose up -d`. Do not open plain HTTP port 8080 to the internet.

For a LAN-only installation instead, set `BIND_ADDRESS` in .env to the VM's LAN address and recreate the container. Open `http://VM-LAN-IP:8080` from the display PC. Keep `COOKIE_SECURE=0` for plain HTTP and restrict access at the network/VM firewall. Docker-published ports require Docker-aware firewall configuration; do not rely on a generic UFW rule alone.

5. Sign in with ADMIN_PASSWORD. Set your actual screen hours and payroll settings. Review the source requirements and enter laboratory estimates before proposing dates.

## Install without Docker — also suitable for Pi

Use a supported 64-bit Linux installation with Python 3.12+ and timezone data. On Debian/Ubuntu, install `python3`, `tzdata`, and `git` using the package manager. Then clone/download the project:

```bash
cd waterworks-calendar
python3 scripts/configure.py
python3 scripts/run.py
```

The server initially listens on 127.0.0.1:8080. Configure Tailscale Serve as above, or set BIND_ADDRESS to the device's LAN IP for LAN access. Native records live under `data/` in the project folder. The generated .env contains the first-start password. Changing it after initial database creation does NOT reset the stored password; see password recovery below.

For automatic startup, create `/etc/systemd/system/waterworks-calendar.service` using your actual username and absolute installation path:

```ini
[Unit]
Description=Waterworks Calendar
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_LINUX_USER
WorkingDirectory=/ABSOLUTE/PATH/waterworks-calendar
ExecStart=/usr/bin/python3 /ABSOLUTE/PATH/waterworks-calendar/scripts/run.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now waterworks-calendar
```

Run the application as a normal user with write access to its data directory. Use one server instance per database. Do not put SQLite on an SMB/NFS share.

## Connect and commission touchscreens

On the display mini PC, install a Linux desktop with an **X11 session** (for example Debian XFCE), Chromium, Python 3, `xrandr`, `xinput`, and `xset`. On Debian the X utilities are supplied by `x11-xserver-utils` and `xinput`; package names can differ on other distributions. Select an X11 login session. The supplied scripts do not configure a Wayland compositor. On a Pi, select a supported X11 session if available; otherwise manually configure its compositor or use the mini-PC recommendation.

1. Start with one monitor; add the second when ready. Connect each installed monitor's video cable AND USB touch cable. Set both monitors to landscape 1920×1080 at 100% scale. Position left at 0,0 and right at 1920,0.
2. Clone/download this repository onto the display PC too, or copy the scripts folder and kiosk.env template. You do not need to start another application server there.
3. Run `xrandr --query` and `xinput list` in a terminal inside the graphical session. Identify each output and touch device; disconnect one USB briefly if names are ambiguous. Identical names may require device IDs or USB-specific naming rules. IDs can change after reboot, so test persistence and use unique names where available.
4. Copy `scripts/kiosk.env.example` to `kiosk.env` in the project root. Enter the server URL and the exact output/device names. Do not put passwords in this file.
5. Run `bash scripts/kiosk.sh` as the logged-in desktop user. It maps each installed touch device to its screen. MONITOR_COUNT=1 starts only the left profile; MONITOR_COUNT=2 starts two independently supervised profiles:

```text
https://YOUR-SERVER/?screen=left&touch=1
https://YOUR-SERVER/?screen=right&touch=1
```

6. Sign in once in each active profile. Session cookies last up to 30 days; restarting the application server invalidates sessions, so sign in again after restart. This release has no unattended sign-in credential stored in the launcher.
7. Copy `scripts/waterworks-kiosk.desktop` into the desktop user's `~/.config/autostart/`, replacing `/ABSOLUTE/PATH` in Exec. Configure desktop auto-login only if appropriate for the room. Disable OS lock-screen/power settings that conflict with the calendar schedule.

The launcher assumes the window manager honors Chromium's requested screen positions. Test your chosen window manager; create window placement rules if it moves both windows to the same screen. Press Alt+F4 to close a kiosk window; the supervisor restarts it. Stop the launcher process to end supervision.

The X11 display-power helper polls `/api/display-state` every 20 seconds and uses DPMS to turn backlights off/on. The endpoint exposes only active state, timezone, and on/off times, not calendar data. It keeps the last known power state on connection failure, rather than guessing closures. The browser also blanks after hours. Actual power behavior, touchscreen mapping, hardware wake, and video decoding require testing on your equipment. A mouse or monitor button may be needed to wake the display; after waking, the browser's “Wake for 30 minutes” button creates an override. The application remains available remotely while monitors sleep.

## Daily operation

- Touch a date to see all its events or add an event. An overflow button opens crowded days.
- Use the dropdown at the bottom of a day to change duty coverage. A confirmation panel selects day/week scope; save to apply. Restore automatic assignment removes the chosen override scope. A separate day override still takes precedence over a week override.
- Use Samples to filter by P-code, open a requirement, confirm its window, enter costs, and record progress. Balance unplanned samples creates proposals; Apply feasible proposals saves them and generates bottle tasks.
- Use Files & media to store permits/schedules. Upload media, press Schedule, select inclusive dates, left/right/both, and optionally a snow/rain/clear/autumn condition. Fresh weather drives condition matching when coordinates are configured; otherwise a seasonal fallback is used. Videos play muted in a small floating panel, leaving most of the calendar available. The newest matching schedule wins when dates overlap. Dismiss temporarily to expose the calendar; refresh restores playback.
- Settings controls screen hours, weekdays, closure dates, effects, optional weather coordinates, and independent payroll markers. Federal labels do not automatically close the facility or shift payday; enter facility-specific events/closures yourself.
- Weather effects use Open-Meteo only if both coordinates are entered. Weather is cached for 15 minutes and considered stale after 30; failed/stale data falls back to the seasonal effect. Coordinates are sent to that provider. Calendar content remains local.
- Export downloads Markdown for any chosen past/current/future date range up to ten years, including crew and sampling records. It does not upload exports to GitHub automatically.
- Data refreshes every 10 seconds. During a network failure an already-open page retains its last loaded view and marks itself OFFLINE; there is no offline edit queue or guaranteed reload without the server.

## Backups, recovery, and upgrades

Settings → Download full backup creates a consistent SQLite snapshot plus uploaded documents/media in a tar.gz. Keep copies off the server. It includes the password hash, settings, staff overrides, events, requirements, and audit log. It does not include the original plaintext .env password; store that separately. A Proxmox snapshot alone is not the full backup policy.

Use `python3 scripts/restore.py backup.tar.gz /path/to/new-empty-data` to extract and integrity-check a trusted backup without overwriting existing records. `scripts/backup.py` also provides a consistent database backup for scheduled native jobs; use the UI backup while uploads are active.

Native restore: stop the service; rename the existing data folder as a safety copy; create a clean data folder; extract a trusted backup into it so `calendar.sqlite3` and `uploads/` are directly inside; restore ownership to the service user; restart. Never unpack untrusted archives as root. Verify event counts and uploaded files after restoration.

Docker restore: stop the service with `docker compose stop`; use the following command to identify the actual volume (do not guess the project-generated name):

```bash
docker inspect "$(docker compose ps -aq calendar)" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
```

Retain a copy of the old volume first. Extract your trusted backup into a clean directory, then copy the restored `calendar.sqlite3` and `uploads/` into the selected volume using a maintenance container or the host volume mountpoint. Restore ownership to UID/GID 10001. Do not leave stale SQLite -wal/-shm files from the previous database alongside the restored database. Restart and verify. Never run `docker compose down -v` as an upgrade step; it deletes stored data.

For a forgotten native password, stop the service and run `python3 scripts/reset-password.py`, then restart. For Docker, stop the app and run that script with DATA_DIR pointing to the mounted volume in a maintenance container; no default recovery password is shipped. The stored password is hashed; it cannot be retrieved from the database.

Upgrade after backing up: pull/extract the new source, review CHANGELOG.md, then `docker compose up -d --build` or restart the native service. Keep a copy of the previous source and backup for rollback. Version 1 initializes its schema without destructive migrations. Login is required again after server restart.

## Validation and physical acceptance

Automated validation covers rotation, Brandon overrides, Wednesday order dates, annual/three-/six-/nine-year seed exceptions, leap/month-end recurrence, budget conflicts, authorization/CSRF, event export, sample-window validation, backups, and navigation. Browser tests cover editing, the modal touch keyboard, shared left/right navigation, sample changes, Markdown downloads, and desktop/mobile rendering.

Before operational use, test both actual USB touch devices after a reboot, display placement, six-row month fit, backlight sleep/wake on the chosen monitors, recovery after server restart, muted playback of your actual media, and a backup restoration. Reconcile all 59 draft requirements with current lab/state records. No physical Raspberry Pi, Proxmox VM, monitor, or laboratory connection was available for this release's tests.

## Project maintenance and GitHub Markdown

This is the maintained guide at `docs/waterworks-calendar.md` in `ncbrandon/calendar`. Each code change should update this guide when behavior/configuration changes and append a dated CHANGELOG.md entry. GitHub is for source and project documentation; keep live data, credentials, permit uploads, backups, and private exports out of it. .gitignore excludes .env and data/.

Run checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --check static/app.js
```

The application and supplied code are version 1.0.0. Future changes requested in this conversation should update the guide and changelog together; there is no autonomous background GitHub updater.

## Changelog

### 2026-11-14 — 1.0.0

- Initial self-hosted implementation, Docker/native packaging, and equipment guide.
- Incorporated corrected Thursday start, Jody/Marcus alternation, Brandon overrides, P-code naming, D01 exclusion, and Wednesday bottle requests.
- Added source-derived draft requirements, window validation, monthly cost proposals, progress tracking, and Markdown export.
- Added touch keyboard, paired screen views, media/effects, and X11 display scripts.
