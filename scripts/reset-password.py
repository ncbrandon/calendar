#!/usr/bin/env python3
"""Stop the server before running. Back up first. Works with native DATA_DIR."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
root=Path(__file__).resolve().parents[1]
path=Path(os.environ.get('DATA_DIR',root/'data'))/'calendar.sqlite3'
if not path.exists(): raise SystemExit('Database not found; set DATA_DIR to the installed data directory.')
password=getpass.getpass('New password (12+ characters): ')
if len(password)<12: raise SystemExit('Password too short; nothing changed.')
if password!=getpass.getpass('Repeat password: '): raise SystemExit('Passwords differ; nothing changed.')
salt=secrets.token_bytes(16)
value={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,300000).hex()}
with sqlite3.connect(path) as con:
    con.execute("UPDATE meta SET value=? WHERE key='password'",(json.dumps(value),))
print('Password changed. Restart the server to invalidate all previous sessions.')
