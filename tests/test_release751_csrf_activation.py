"""Release 751 strict-CSRF disposable validation and DEV activation guard."""
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME

ROOT = Path(__file__).resolve().parents[1]
TOGGLE = ROOT / "scripts/tracker-csrf-dev751.sh"

@pytest.mark.parametrize("scheme", ("http", "https"))
def test_751_existing_strict_root_rejects_forged_and_accepts_signed(scheme, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    with TestClient(app, base_url=scheme + "://testserver") as c:
        assert c.get("/compounds").status_code == 200
        token = c.cookies.get(COOKIE_NAME)
        assert token and token.startswith("v1.")
        for headers in ({}, {HEADER_NAME: "forged-751"}):
            denied = c.post("/compounds", data={"name": "UNSIGNED-751"},
                            headers=headers, follow_redirects=False)
            assert denied.status_code == 403
        # Signed request reaches form validation; never creates a record.
        invalid = c.post("/compounds", data={"name": ""},
                         headers={HEADER_NAME: token}, follow_redirects=False)
        assert invalid.status_code == 422
        assert invalid.headers.get("x-tracker-csrf-report") == "valid"
        assert "UNSIGNED-751" not in c.get("/compounds").text

def test_751_live_activation_has_guarded_rollback_and_readonly_smoke():
    contents = TOGGLE.read_text()
    for required in ("tracker-dev", "TRACKER_CSRF_ENFORCE=1", "EnvironmentFile=",
                     "systemctl daemon-reload", "systemctl restart tracker.service",
                     "ROLLBACK_751=RESTORING_REPORT_ONLY",
                     "HTTP_751_UNSIGNED_WRITE=DENIED", "STRICT_CSRF_751_DEV=ENABLED",
                     "case \"$MODE\" in enable|disable|status)"):
        assert required in contents, required
    for forbidden in ("git reset --hard", "TRACKER_ORIGIN_GUARD=0",
                      "systemctl restart tracker-prod", "DROP TABLE",
                      "UPDATE users", "/opt/tracker/data/"):
        assert forbidden not in contents

def test_751_full_browser_and_backend_qualification_precedes_dev_toggle():
    q = (ROOT / "scripts/tracker-qualify751.sh").read_text()
    ins = (ROOT / "scripts/tracker-install751.sh").read_text()
    scoped = (ROOT / "scripts/tracker-release-scoped751.sh").read_text()
    assert "PrivateNetwork=yes required" in q
    assert "tracker-browser-qualify.sh" in q
    assert "RELEASE_751_INSTALLED_DEV=UNMODIFIED" in q
    assert "--targeted-strict dose602" in q
    assert "RELEASE_751_TARGETED_DOSE602=PASSED" in q
    assert "RELEASE_751_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY" in q
    b = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    assert 'TARGETED_MODULE" == dose602' in b
    assert "TARGETED_DOSE602_HTTP_HTTPS=PASSED" in b
    assert "tracker-release-scoped751.sh" in q
    assert "RELEASE_751_FULL_BACKEND_PREFLIGHT=PASSED" in q
    assert 'tracker-backend-parity751.py' in q
    assert 'RELEASE_751_BACKEND_BASELINE_PARITY=PASSED' in (
        ROOT / "scripts/tracker-backend-parity751.py"
    ).read_text()
    assert 'timeout 1200 "$PY" -m pytest' in runner
    assert 'FULL BACKEND BASELINE PARITY GATE PASSED' in runner
    assert q.index("RELEASE_751_FULL_BACKEND_PREFLIGHT=PASSED") < q.index(
        "RELEASE_751_TARGETED_DOSE602=STARTED"
    )
    for required in ("tests/test_core_user_db394.py",
                     "tests/test_release604_preflight.py"):
        assert required in scoped
        assert required in q
    assert "--full-suite" in ins
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'timeout 1800 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"' in runner
    assert 'timeout 1200 "$PY" -m pytest' in runner
    assert 'tracker-csrf-dev751.sh" enable "$TARGET"' in ins
    assert ins.index("--full-suite") < ins.index('tracker-csrf-dev751.sh" enable')
    for path in ("tests/test_csrf_all_registered_negative705.py",
                 "tests/test_release520_csrf_multipart.py",
                 "tests/test_release521_strict_auth_compatibility.py",
                 "tests/test_release751_csrf_activation.py"):
        assert path in scoped
    for script in ("tracker-qualify751.sh", "tracker-install751.sh",
                   "tracker-release-scoped751.sh", "tracker-csrf-dev751.sh"):
        result = subprocess.run(["bash","-n",str(ROOT/"scripts"/script)],
                                capture_output=True,text=True)
        assert result.returncode == 0, (script,result.stderr)
