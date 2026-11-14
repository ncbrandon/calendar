# Validation — 1.0.0

Completed November 14, 2026 in the build environment.

- **23 automated Python/API/launcher tests passed.** Covers rotation boundaries, Brandon overrides, Wednesday bottle dates, imported exceptions, month-end/leap recurrences, budget conflicts, unknown costs, login/CSRF, event persistence/export, sample-window validation, backups, shared navigation, concurrent-edit rejection, month rollover, and idle reset.
- **Chromium browser workflows passed with no page errors.** Checked modal touch keyboard input, event creation, independent left/right pages sharing navigation, weekly coverage, sample editing, bottle event generation, GIF upload/scheduling/playback, Markdown download, 1920×1080 kiosk fit, paired desktop rendering, and mobile rendering.
- **Docker image built and ran successfully** as nonroot with a read-only application filesystem and writable data volume. Checked timezone handling, 59 seeded requirements, login, writes, and records surviving container restart.
- **Backup/restore script round trip passed**, including SQLite integrity validation.
- JavaScript syntax, Python compilation, and Bash launcher syntax checks passed.

Not physically tested: Proxmox host/VM installation, ARM64/Pi execution, USB touchscreen mapping, monitor DPMS behavior, physical wake, actual laboratory delivery, and user-selected video codecs. The included source requirements remain drafts pending review; this test report does not certify regulatory compliance.

## One-monitor update — November 14, 2026

Four additional isolated launcher tests passed using fake X11/browser commands: default single-screen startup with no second-hardware configuration, explicit two-screen startup/mapping, rejection of incomplete dual-screen settings, and rejection of invalid monitor counts. These exercise the real Bash launcher without controlling physical displays. The existing 19 calendar/API tests still pass. No calendar rendering, database, or regulatory rules changed.
