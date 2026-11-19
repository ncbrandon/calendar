# Ordering checklist

Use this page on order day. Screen and touch-frame prices were checked **November 19, 2026**. Everything else
is from **November 14, 2026**. Check the price at checkout; monitors go on and off sale often.

## 1. Pick the build

| If you want... | Order | Screens | Total for two screens | Total for one screen now |
|---|---|---|---|---|
| The most dependable wall (recommended) | [Variant A](variant-a-recommended.md) | 2 x ViewSonic TD3207, touch built in | about $2,420 | about $1,235 |
| The best price with one Pi per screen | [Variant C](variant-c-middle.md) | 2 x 32" monitor + stick-on IR touch frame | about $1,060 | about $555 |
| The cheapest | [Variant B](variant-b-budget.md) | Same screens as C, one Pi drives both | about $960 | about $570 |
| 43" screens | [Variant D](variant-d-premium.md) | Elo 4303L. **Discontinued**, leftover stock only | about $3,400 | about $1,700 |

**Not in any parts list:** the server. Variants A, C and D run it on your existing Proxmox machine. In Variant B the Pi runs it.

## 2. Before you click "buy"

- [ ] **Two screens or one?** Starting with one is fine. See [Start with one screen](start-with-one-screen.md) for what to leave for later.
- [ ] **Monitors:** both from the same seller and the same model number, so they match.
- [ ] **Return window:** at least 30 days on the monitors and touch frames. You will bench-test before mounting.
- [ ] **"Search" links in the parts lists** (wall mounts, power strip, cord cover, hook-and-loop strips, Ethernet cables, touch frames):
      these are not one exact product. Pick a well-reviewed listing that matches the size or spec in the list.
- [ ] **Wall mounts:** must fit VESA 100x100 (all 32" choices here) and hold the monitor's weight. Low-profile, fixed or slight tilt.
- [ ] **Raspberry Pi 5:** the 2 GB model is enough for a screen. Buy the official 27W power supply; a phone charger causes random reboots.

## 3. Variant-specific

### Variant A (ViewSonic TD3207)

- [ ] ViewSonic TD3207: **$1,029.99** at [ViewSonic](https://www.viewsonic.com/us/td3207.html) and [CDW](https://www.cdw.com/product/viewsonic-td3207-1080p-touch-screen-monitor-with-24-7-operation-hdmi-di/7650751); $1,049.99 at Best Buy and Walmart.
      A refurbished unit is [$771.99 from ViewSonic](https://www.viewsonic.com/edu/td3207-s.html), but it has only a 90-day warranty.
- [ ] The touch layer is built in. ViewSonic says it uses the standard Linux touch driver; it does not name the Pi 5,
      so bench-test the first one before hanging it.

### Variants B and C (monitor + IR touch frame)

- [ ] **Monitor:** ViewSonic VA3209M, **$149.99** at [ViewSonic](https://www.viewsonic.com/us/va3209m.html). Or the
      Samsung Odyssey G5 **G50F** (model LS32FG502ENXZA), **$209.99** at [Newegg](https://www.newegg.com/samsung-ls32fg502enxza-32-qhd-max-180-hz-ips-black/p/N82E16824027385).
      Do not buy the G51F by mistake: it is a different model and often cheaper.
- [ ] **Touch frame: order ONE first.** 32", 10-point, USB, "HID" or "driver free" in the listing. $170 to $260 on Newegg and eBay.
      A listing that says it supports Linux or Raspberry Pi is a small plus. Ask the seller for a dimension drawing.
- [ ] **Measure before ordering the frame:** the frame's inner opening must be at least the monitor's lit picture
      area (about 27.5" x 15.5" on a 32" monitor). Measure the actual monitor, as bezels differ between models.
- [ ] When the first frame arrives, run the [bench test](variant-c-middle.md#bench-test-the-frame-before-mounting-anything).
      If the Pi detects it, order the second frame from the same listing. If two-finger swipe does not work,
      that is fine: the « and » buttons change the year.
- [ ] Why this is a reasonable risk, and what to buy if it fails: [Will the touch frame work on a Pi 5?](variant-c-middle.md#will-the-touch-frame-work-on-a-pi-5)

### Variant D (Elo 4303L)

- [ ] **Discontinued.** Before ordering, get one seller to confirm **two** units in stock (Touchwindow, Tecisoft and Barcodes Inc. listed about $1,190 to $1,300),
      or ask Elo or a reseller for the current 43" replacement model.

## 4. After it arrives

1. Set up the server: [server-setup.md](server-setup.md).
2. On a table, set up one Pi and one screen: [kiosk-setup.md](kiosk-setup.md). Run the bench test.
3. Only then mount: [mounting.md](mounting.md).

Still not tested on real hardware: the Pi 5 with any of these screens, the monitor switching off after hours, and
two-finger swipes on an IR frame. The bench test covers the touch questions. For the monitor, run step 4 of the testing
section in [kiosk-setup.md](kiosk-setup.md#testing) (screens go dark, monitor switches off, a tap wakes it) before mounting.
