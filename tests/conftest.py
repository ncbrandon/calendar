import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("OPSBOARD_DATA", str(tmp_path))
    from app import db

    db.init()
    connection = db.connect()
    yield connection
    connection.close()
