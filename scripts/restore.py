#!/usr/bin/env python3
"""Restore a trusted backup into a NEW, EMPTY directory; never overwrite live data.

Usage: python3 scripts/restore.py backup.tar.gz /path/new-data-directory
Stop the server before switching its data folder/volume to the restored copy.
"""
from pathlib import Path
import sqlite3
import sys
import tarfile
if len(sys.argv)!=3:raise SystemExit('Usage: restore.py backup.tar.gz /path/new-empty-data-directory')
archive=Path(sys.argv[1]).resolve();target=Path(sys.argv[2]).resolve()
if target.exists() and any(target.iterdir()):raise SystemExit('Target must be empty; existing data was not changed.')
target.mkdir(parents=True,exist_ok=True)
with tarfile.open(archive,'r:gz') as f:
    for member in f.getmembers():
        path=Path(member.name)
        if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():raise SystemExit('Unsafe archive member rejected.')
        if member.name!='calendar.sqlite3' and (not path.parts or path.parts[0]!='uploads'):raise SystemExit('Unexpected backup contents rejected.')
    f.extractall(target,filter='data')
with sqlite3.connect(target/'calendar.sqlite3') as c:
    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Restored database integrity check failed.')
if not (target/'uploads').is_dir():raise SystemExit('Uploads directory missing.')
print('Restored and integrity-checked:',target)
print('Stop the app, retain its old data as a safety copy, switch to this folder, then restart and verify.')
