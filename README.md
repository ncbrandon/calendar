# Waterworks Calendar

A self-hosted two-screen touchscreen calendar and well-sampling planner for West Jefferson.

**[Equipment, installation, and operating guide](docs/waterworks-calendar.md)**

Quick start (Python 3.12+, no Python dependencies):

```bash
python3 scripts/configure.py
# Privately open .env to obtain the generated administrator password.
python3 scripts/run.py
```

Open http://127.0.0.1:8080. For Docker, use `docker compose up -d --build` after configuring .env. Read the guide for Proxmox, Raspberry Pi, private online access, and two-screen kiosk installation.

The source schedule is preloaded as 59 **draft** requirements. Review before planning. No live data or credentials are included. New permit upload is document storage plus manual requirement entry, not AI interpretation.

Run tests: `python3 -m unittest discover -s tests -v`.
