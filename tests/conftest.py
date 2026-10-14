import pytest
from participation_tracker.db.database import Database
from participation_tracker.db.repository import Repository

@pytest.fixture
def repo(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    yield Repository(db)
    db.close()
