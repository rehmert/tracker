import os
import tempfile

# Must be set before `app` is imported so the DB and uploads go to a temp dir.
os.environ["TRACKER_DATA_DIR"] = tempfile.mkdtemp(prefix="tracker-test-")
os.environ.pop("TRACKER_USER", None)
os.environ.pop("TRACKER_PASS", None)
