import pytest

from bzoj import storage


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'local' / 'bzoj.sqlite3')
