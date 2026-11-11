from __future__ import annotations

import pytest

from price_monitor import db

@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.initialize(connection)
    yield connection
    connection.close()
