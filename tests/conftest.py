"""Always isolate the test suite from the running Tracker database."""
import os
import tempfile
from pathlib import Path

# pytest imports conftest before importing test modules or app.db. Always use
# an independently generated directory, even when TRACKER_DATA_DIR is set.
_TEST_DIR = tempfile.TemporaryDirectory(prefix="tracker-pytest-isolated-")
TEST_DATA_DIR = Path(_TEST_DIR.name).resolve()
os.environ["TRACKER_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ.pop("TRACKER_USER", None)
os.environ.pop("TRACKER_PASS", None)


def pytest_sessionstart(session):
    """Refuse to run if another import initialized the app against a different DB."""
    import sys
    cfg = sys.modules.get("app.config")
    if cfg is not None and Path(cfg.DATA_DIR).resolve() != TEST_DATA_DIR:
        raise RuntimeError("Refusing to test: Tracker database was initialized outside the isolated test directory")


def pytest_sessionfinish(session, exitstatus):
    # SQLAlchemy connections are usually released at process exit; keeping the
    # temp dir until process exit avoids Windows file-lock teardown errors.
    pass
