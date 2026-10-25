import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("TRACKER_DATA_DIR", BASE_DIR.parent / "data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads" / "coa"
LAB_DIR = DATA_DIR / "uploads" / "labs"
DB_PATH = DATA_DIR / "tracker.db"
DB_URL = f"sqlite:///{DB_PATH}"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_UPLOAD_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
CURRENCY = os.getenv("TRACKER_CURRENCY", "$")

# Optional HTTP Basic auth. If both are set, every page requires them.
AUTH_USER = os.getenv("TRACKER_USER", "")
AUTH_PASS = os.getenv("TRACKER_PASS", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LAB_DIR.mkdir(parents=True, exist_ok=True)

WEIGHT_UNIT = os.getenv("TRACKER_WEIGHT_UNIT", "lb").strip().lower()
if WEIGHT_UNIT not in ("kg", "lb"):
    WEIGHT_UNIT = "lb"
