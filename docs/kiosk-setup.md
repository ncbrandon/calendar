# Set up the wall-screen computers

A "wall-screen computer" is the Raspberry Pi (or mini PC) plugged into a touch monitor. It only runs a
full-screen browser pointed at the server.

- **Variants A, C, D:** two Pis, one per screen. Do every step once per Pi, with `left` on one and `right` on the other.
- **Variant B:** one Pi with both screens. Do the steps once, with `both`.

Tools: a PC with an SD card reader, a USB keyboard and mouse for first setup.

## Steps

1. On your PC, install **Raspberry Pi Imager** from https://www.raspberrypi.com/software/.
2. Insert the microSD card. In Imager choose your Pi model, then **Raspberry Pi OS (64-bit)** (the full desktop
   version, not Lite), then the card.
3. When Imager offers to customise settings, set:
   - Hostname: `wall-left` or `wall-right` (or `wall` for Variant B)
   - A user name and password you will remember
   - Your Wi-Fi name and password (skip if using Ethernet, which is steadier)
   - Your time zone
   - Enable SSH, so you can fix things later without a keyboard on the wall
4. Write the card, put it in the Pi, connect the monitor's HDMI and USB (touch) cables, then power the Pi.
   The Pi 5 has two micro-HDMI ports: use the one nearest the power plug for a single screen.
5. Wait for the desktop. Touch should already move the pointer.
6. **Variant B only:** install the server now ([server-setup.md, option 2](server-setup.md)), then come back.
7. Open a terminal and fetch the program (skip if step 6 already did):

   ```bash
   git clone https://github.com/YOUR-NAME/opsboard.git ~/opsboard-repo
   ```

8. Run the installer with your server address, the side, and the screen token from the server install.

   Left Pi:

   ```bash
   bash ~/opsboard-repo/kiosk/install-kiosk.sh http://192.168.1.50:8080 left YOUR_SCREEN_TOKEN
   ```

   Right Pi:

   ```bash
   bash ~/opsboard-repo/kiosk/install-kiosk.sh http://192.168.1.50:8080 right YOUR_SCREEN_TOKEN
   ```

   Variant B (one Pi, both screens):

   ```bash
   bash ~/opsboard-repo/kiosk/install-kiosk.sh http://localhost:8080 both YOUR_SCREEN_TOKEN
   ```

9. Turn on automatic login:

   ```bash
   sudo raspi-config
   ```

   Choose **System Options**, **Boot / Auto Login**, **Desktop Autologin**.
10. **Variant B only:** still in `raspi-config`, choose **Advanced Options**, **Wayland**, **X11**. One computer
    can only tie two touch panels to two monitors reliably on X11.
11. Reboot:

    ```bash
    sudo reboot
    ```

12. The calendar should come up full screen within a minute.

## Testing

1. Tap a day. The day dialog opens. Tap the Title box: the on-screen keyboard appears. Add a test event.
2. Check that the event shows on your PC's web page within a few seconds, then delete it.
3. Tap the right arrow on one screen. Both screens should move a month.
4. On the web page, under Settings, set "Screens go dark at" to a minute from now and save. The screens should go
   black, then the monitors should switch off about 15 seconds later. Tap a screen: it should come back for
   5 minutes. Put the real hours back.

## Calibration and fixes

All settings are in `~/.config/opsboard/kiosk.env` on the wall-screen computer. Reboot after changing them.
The log is `~/.config/opsboard/kiosk.log`.

| Problem | Fix |
|---|---|
| Months are on the wrong screens (Variant B) | `SWAP_SCREENS=1` |
| Touching the left screen acts on the right (Variant B) | `SWAP_TOUCH=1` |
| Touch covers both screens at once (Variant B) | Run `xinput list`, find the two touch panels, and put a word from their name in `TOUCH_MATCH=` |
| A tap does not wake the monitors | Some monitors ignore everything while asleep. Set `HARDWARE_SLEEP=0`: the screen shows a black page instead of powering off |
| Touch is offset by an inch or so (IR frames) | The frame is not square to the picture. Re-seat it, or run the calibration tool that came with the frame |
| Everything is too small or too large | The page scales to the screen height. Set the monitor to its native resolution (1920x1080) in the desktop's Screen Configuration |
| Stuck on "Reconnecting to the server" | The server address changed or the server is down. Check the reservation from server-setup step 8 |
| A dialog says Chromium did not shut down correctly | Tap it away once; the launcher clears that flag on the next start |
| Videos play without sound | Check the monitor is the sound output (right-click the speaker icon) and the video is not marked Muted |

## Using a mini PC instead of a Pi

Any small PC with Debian 12 or 13 and a desktop works with the same `install-kiosk.sh`. Skip `raspi-config`: set
automatic login in your display manager, and choose the X11 session at the login screen for `both` mode.
