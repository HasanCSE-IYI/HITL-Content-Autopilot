import sys
import os
import socket
import tempfile
import pytest

# Ensure the project root directory is on sys.path for all test runs
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

@pytest.fixture(autouse=True, scope="session")
def block_external_network_calls():
    """
    🛡️ Ironclad Credit Protection Firewall:
    Intercepts all outbound socket connections during automated tests.
    If ANY test ever attempts an unmocked network call to an external API
    (e.g., api.openai.com, generativelanguage.googleapis.com, amazon.com),
    it is immediately intercepted and blocked with a RuntimeError to guarantee
    ZERO live API credits or tokens are ever consumed during test runs.
    """
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else str(address)
        # Allow internal localhost loopback if ever needed for local test servers
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise RuntimeError(
            f"🚫 [CREDIT PROTECTION BLOCKED] Outbound connection to '{host}' blocked during test run! "
            f"All tests must use offline mocks to guarantee zero API credit consumption."
        )

    socket.socket.connect = guarded_connect
    yield
    socket.socket.connect = original_connect

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
