#!/usr/bin/env python3
from pathlib import Path
import os
import sys
root=Path(__file__).resolve().parents[1]
if not (root/'.env').exists(): raise SystemExit('Run python3 scripts/configure.py first.')
for line in (root/'.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key,value=line.split('=',1)
        os.environ.setdefault(key,value)
os.environ.setdefault('HOST',os.environ.get('BIND_ADDRESS','127.0.0.1'))
os.execv(sys.executable,[sys.executable,str(root/'server.py')])
