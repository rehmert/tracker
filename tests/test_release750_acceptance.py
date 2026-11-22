"""Release 750: two real secondary-account sessions, independent records."""
import sqlite3
from app.multiuser_audit474 import audit474
from scripts.secondary_integration440_support import browser, _hidden, _login, _post_form, _counts

def test_750_distinct_authenticated_accounts_reject_cross_account_signed_replay(browser):
    client, root = browser
    _login(client, 2)
    form = client.get("/secondary/supplies")
    assert form.status_code == 200
    original = (_hidden(form.text, "csrf_token"), _hidden(form.text, "submission_token"))
    _post_form(client, "/secondary/supplies", "/secondary/supplies", {
        "name": "QA750-OWNER-2", "kind": "bac_water", "quantity": "7", "notes": "",
    })
    owner2 = _counts(root, 2)
    assert owner2["supplies"] == 1 and owner2["change_audit"] == 1
    assert all(v == 0 for v in _counts(root, 3).values())
    _login(client, 3)
    assert "QA750-OWNER-2" not in client.get("/secondary/supplies").text
    replay = client.post("/secondary/supplies", data={
        "csrf_token": original[0], "submission_token": original[1],
        "name": "QA750-REPLAY-REJECT", "kind": "bac_water", "quantity": "3", "notes": "",
    }, follow_redirects=False)
    assert replay.status_code in (400, 401, 403), replay.status_code
    assert all(v == 0 for v in _counts(root, 3).values())
    _post_form(client, "/secondary/supplies", "/secondary/supplies", {
        "name": "QA750-OWNER-3", "kind": "needle", "quantity": "12", "notes": "",
    })
    assert _counts(root, 3)["supplies"] == 1
    assert _counts(root, 3)["change_audit"] == 1
    assert _counts(root, 2) == owner2
    _login(client, 2)
    assert "QA750-OWNER-3" not in client.get("/secondary/supplies").text
    assert "QA750-OWNER-2" in client.get("/secondary/supplies").text
    for uid, expected in ((2, "QA750-OWNER-2"), (3, "QA750-OWNER-3")):
        with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
            assert db.execute("SELECT name FROM supplies").fetchall() == [(expected,)]
            assert db.execute("SELECT action FROM change_audit").fetchall() == [
                ("secondary_supply_intake438",)]
    assert not (root / "tracker.db").exists()

def test_750_main_app_multiuser_cutover_is_still_disabled():
    report = audit474()
    assert report["source_only"] is True
    assert report["full_main_app_cutover_ready"] is False
    assert report["runtime_security_proven"] is False
    blockers = {x["id"] for x in report["blocking_items"]}
    assert {"ADMIN_ONLY_SCOPE", "ADMIN_ONLY_ENGINE",
            "FOOD_GLOBAL_ENGINE", "ROUTE_PARITY_NOT_PROVEN"} <= blockers


def test_750_disposable_browser_replay_has_private_child_even_in_deployer():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "scripts/tracker-release-scoped750.sh").read_text()
    assert 'mktemp -d "$TRACKER_DATA_DIR/browser750.XXXXXXXX"' in source
    assert 'stat -c %a "$PRIVATE_REPLAY"' in source
    assert 'TRACKER_DATA_DIR="$PRIVATE_REPLAY"' in source
    assert 'rmdir -- "$PRIVATE_REPLAY"' in source
