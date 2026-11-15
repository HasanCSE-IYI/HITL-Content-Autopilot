import sys
import os
import tempfile
import pytest

# Ensure the project root directory is on sys.path for all test runs
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

@pytest.fixture(autouse=True, scope="session")
def isolate_test_database():
    """
    Ensures all pytest runs use an isolated temporary SQLite database
    so the production data/autopilot.db is NEVER polluted by test runs.
    """
    import core.database as db
    test_db_path = os.path.join(tempfile.gettempdir(), "pytest_hitl_isolated.db")
    
    # Clean previous test db if exists
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    # Isolate test database in core.database
    original_path = getattr(db, "DB_PATH", db.resolve_db_path())
    db.set_database_path(test_db_path)

    yield test_db_path

    # Restore production database after test session finishes
    db.set_database_path(original_path)
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass
