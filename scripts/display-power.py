#!/usr/bin/env python3
"""X11 monitor power control. The browser itself only provides a black overlay.

Uses public read-only /api/display-state, which reveals only active hours.
Retains last known state on network failure; cannot wake unsupported monitors.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from datetime import datetime
from zoneinfo import ZoneInfo
import shlex
root=Path(__file__).resolve().parents[1]
config={}
for line in (root/'kiosk.env').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1); tokens=shlex.split(value)
        config[key]=tokens[0] if tokens else ''
url=config['CALENDAR_URL'].rstrip('/')+'/api/display-state'
last_active=None
cache_file=root/'work-hours-cache.json'
cache=None
if cache_file.exists():
    try: cache=json.loads(cache_file.read_text())
    except (OSError,ValueError): pass
while True:
    try:
        with urlopen(url,timeout=5) as response: state=json.load(response)
        active=state['active']
        cache={'state':state,'fetched':time.time()}
        cache_file.write_text(json.dumps(cache))
    except Exception:
        # Last exact active state is safer than guessing holidays or weekdays.
        active=cache['state']['active'] if cache else True
    try:
        if active!=last_active:
            subprocess.run(['xset','+dpms'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['xset','dpms','0','0','0'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['xset','dpms','force','on' if active else 'off'],check=True,stdout=subprocess.DEVNULL)
            last_active=active
        elif not active:
            # Some touches cause X to wake the monitor; put it back to sleep.
            subprocess.run(['xset','dpms','force','off'],check=False,stdout=subprocess.DEVNULL)
    except (OSError,subprocess.CalledProcessError) as error:
        print('Display power command failed:',error,flush=True)
    time.sleep(20)
