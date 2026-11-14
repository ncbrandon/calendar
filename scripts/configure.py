#!/usr/bin/env python3
"""Generate first-install credentials without printing them to shared logs."""
from pathlib import Path
import secrets
import os
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists(): raise SystemExit('.env already exists; retained without changes.')
password=secrets.token_urlsafe(24)
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write(f'ADMIN_PASSWORD={password}\nBIND_ADDRESS=127.0.0.1\nPORT=8080\nCOOKIE_SECURE=0\n')
print('Created .env (owner read/write only). Open it privately to see ADMIN_PASSWORD.')
print('Docker: docker compose up -d --build')
print('Without Docker: python3 scripts/run.py')
