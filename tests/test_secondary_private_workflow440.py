"""Release 440 full private secondary workflow, isolated for xdist loadfile scheduling.

All original endpoint checks, audit assertions, and cross-account checks
remain intact. Each invocation receives a disposable standalone workspace.
"""
import sqlite3
from datetime import datetime

from scripts.secondary_integration440_support import (
    browser, _hidden, _login, _post_form, _counts,
)

def test_full_private_browser_workflow_with_audits_and_no_cross_account_data(browser):
    client, root = browser
    _login(client, 2)

    _post_form(
        client, "/secondary/inventory", "/secondary/inventory/compounds",
        {
            "name": "PRIVATE-440-ALPHA", "category": "peptide",
            "primary_unit": "mg", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/inventory", "/secondary/inventory/vials",
        {
            "compound_id": "1", "label": "PRIVATE-440-VIAL",
            "content_value": "10", "content_unit": "mg",
            "form": "lyophilized", "volume_ml": "", "lot": "440",
            "cap_color": "Blue", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/reconstitution", "/secondary/reconstitution",
        {"vial_id": "1", "volume_ml": "2"},
    )
    _post_form(
        client, "/secondary/doses/new", "/secondary/doses/new",
        {
            "vial_id": "1",
            "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "amount": "2", "unit": "mg",
            "site": "", "notes": "PRIVATE-440-DOSE",
        },
    )
    _post_form(
        client, "/secondary/vitals/new", "/secondary/vitals/new",
        {
            "measured_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "weight": "240", "weight_unit": "lb",
            "systolic": "122", "diastolic": "78",
            "pulse_bpm": "67", "context": "PRIVATE-440-VITAL",
            "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies", "/secondary/supplies",
        {
            "name": "PRIVATE-440-BAC", "kind": "bac_water",
            "quantity": "5", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies", "/secondary/supplies",
        {
            "name": "PRIVATE-440-NEEDLE", "kind": "needle",
            "quantity": "10", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies/use", "/secondary/supplies/use",
        {
            "supply_id": "1", "reference": "reconstitution:1",
            "amount": "2", "notes": "Water actually consumed",
        },
    )
    _post_form(
        client, "/secondary/supplies/use", "/secondary/supplies/use",
        {
            "supply_id": "2", "reference": "dose:1",
            "amount": "1", "notes": "Needle actually consumed",
        },
    )

    correction_page = client.get("/secondary/reconcile/vials/1")
    assert correction_page.status_code == 200
    assert "8 mg" in correction_page.text
    _post_form(
        client, "/secondary/reconcile/vials/1", "/secondary/reconcile/correct",
        {
            "vial_id": "1",
            "snapshot": _hidden(correction_page.text, "snapshot"),
            "label": "PRIVATE-440-CORRECTED",
            "lot": "440", "cap_color": "Blue",
            "status": "in_use",
            "reason": "Physical vial label verified",
        },
    )

    for route, expected in (
        ("/secondary/overview", "Private Workspace Overview"),
        ("/secondary/vitals", "PRIVATE-440-VITAL"),
        ("/secondary/doses", "PRIVATE-440-ALPHA"),
        ("/secondary/inventory", "PRIVATE-440-CORRECTED"),
        ("/secondary/reconcile", "8 mg"),
        ("/secondary/supplies", "PRIVATE-440-BAC"),
        ("/secondary/supplies/use", "Reconstitution #1"),
        ("/secondary/readiness", "Workspace Readiness"),
    ):
        page = client.get(route)
        assert page.status_code == 200, (route, page.status_code)
        assert expected in page.text, (route, expected)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        vial = db.execute("""
            SELECT status,label,volume_ml FROM vials
            WHERE id=1
        """).fetchone()
        supplies = db.execute("""
            SELECT id,remaining_qty FROM supplies ORDER BY id
        """).fetchall()
        usage_links = db.execute(
            "SELECT COUNT(*) FROM preparation_supplies"
        ).fetchone()[0]
        audits = db.execute("""
            SELECT action FROM change_audit ORDER BY id
        """).fetchall()
        assert vial == ("in_use", "PRIVATE-440-CORRECTED", 2.0)
        assert supplies == [(1, 3.0), (2, 9.0)]
        assert usage_links == 1
        assert [r[0] for r in audits] == [
            "secondary_supply_intake438",
            "secondary_supply_intake438",
            "secondary_supply_use439",
            "secondary_supply_use439",
            "secondary_correction437",
        ]

    assert _counts(root, 2)["dose_logs"] == 1
    assert _counts(root, 2)["vital_readings"] == 1
    assert all(value == 0 for value in _counts(root, 3).values())
    assert not (root / "tracker.db").exists()

    _login(client, 3)
    for route, secret in (
        ("/secondary/inventory", "PRIVATE-440-ALPHA"),
        ("/secondary/doses", "PRIVATE-440-ALPHA"),
        ("/secondary/vitals", "PRIVATE-440-VITAL"),
        ("/secondary/supplies", "PRIVATE-440-BAC"),
        ("/secondary/reconcile", "PRIVATE-440-CORRECTED"),
    ):
        page = client.get(route)
        assert page.status_code == 200
        assert secret not in page.text
