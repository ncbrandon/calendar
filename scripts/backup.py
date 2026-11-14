#!/usr/bin/env python3
"""Consistent native backup. Usage: python3 scripts/backup.py /path/backup.tar.gz"""
from pathlib import Path
import os
import sqlite3
import sys
import tarfile
import tempfile
root=Path(__file__).resolve().parents[1]
data=Path(os.environ.get('DATA_DIR',root/'data')).resolve()
if len(sys.argv)!=2:raise SystemExit('Usage: backup.py /path/to/new-backup.tar.gz')
target=Path(sys.argv[1]).resolve()
if target.exists():raise SystemExit('Backup target already exists; choose a new filename.')
if not (data/'calendar.sqlite3').exists():raise SystemExit('Database not found.')
target.parent.mkdir(parents=True,exist_ok=True)
# UI backup locks application writes and is preferred when files are being uploaded.
with tempfile.TemporaryDirectory() as temp:
    snapshot=Path(temp)/'calendar.sqlite3'
    with sqlite3.connect(data/'calendar.sqlite3') as source,sqlite3.connect(snapshot) as dest:source.backup(dest)
    with tarfile.open(target,'w:gz') as archive:
        archive.add(snapshot,arcname='calendar.sqlite3')
        archive.add(data/'uploads',arcname='uploads')
print('Backup created:',target)
