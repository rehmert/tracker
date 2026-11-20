"""Release 709: exact ten food/COA CSRF positive route acceptance contract."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.tracker_csrf_reconcile627 import (
    build,
    POST_627_UNQUALIFIED_ROUTES,
    POST_643_UNQUALIFIED_COA_ROUTES,
    POST_645_UNQUALIFIED_COA_ROUTES,
    POST_647_UNQUALIFIED_COA_ROUTES,
    POST_654_PLUS_UNQUALIFIED_ROUTES,
)

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests/browser/test_csrf_food_coa709.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
WORKER = ROOT / "scripts/tracker-csrf-positive709.sh"


def literal_routes(name: str) -> set[tuple[str, str]]:
    tree = ast.parse(BROWSER.read_text(encoding="utf-8"))
    matches = [
        node for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    assert len(matches) == 1
    call = matches[0].value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Name)
    assert call.func.id == "frozenset"
    assert len(call.args) == 1
    return set(ast.literal_eval(call.args[0]))


def test_709_exact_ten_new_routes_are_historically_unqualified():
    food = literal_routes("FOOD_ROUTES")
    coa = literal_routes("COA_ROUTES")
    report = build()
    ledger = {(r["method"], r["path"]) for r in report["remaining_routes"]}
    expected = (
        POST_627_UNQUALIFIED_ROUTES |
        POST_643_UNQUALIFIED_COA_ROUTES |
        POST_645_UNQUALIFIED_COA_ROUTES |
        POST_647_UNQUALIFIED_COA_ROUTES |
        {
            ("POST", "/food/saved/{product_id}/edit"),
            ("POST", "/coas/{cid}/attachments/identifiers"),
        }
    )
    assert len(food) == 4
    assert len(coa) == 6
    assert not food & coa
    assert len(expected) == 10
    assert food | coa == expected
    assert expected <= ledger
    assert expected <= (
        POST_627_UNQUALIFIED_ROUTES |
        POST_643_UNQUALIFIED_COA_ROUTES |
        POST_645_UNQUALIFIED_COA_ROUTES |
        POST_647_UNQUALIFIED_COA_ROUTES |
        POST_654_PLUS_UNQUALIFIED_ROUTES
    )
    assert report["remaining_without_positive_source_witness"] == 92
    assert report["global_enforcement_authorized"] is False


def test_709_real_http_https_chromium_tokenless_forged_and_sql_positive():
    source = BROWSER.read_text(encoding="utf-8")
    for marker in (
        'TRACKER_TEST_ISOLATED") == "1"',
        'TRACKER_TEST_STRICT_CSRF") == "1"',
        'DATA.parent.parent == Path("/tmp").resolve()',
        'window.trackerCsrfToken?.()',
        'cookie["value"] == token',
        'missing.status == 403',
        'forged.status == 403',
        'assert unchanged() == original',
        'accepted.headers.get("x-tracker-csrf-report") == "valid"',
        'accepted.status == status',
        'assert seen == FOOD_ROUTES',
        'assert seen == COA_ROUTES',
        '@pytest.mark.parametrize("scheme", ("http", "https"))',
        'FROM tracker_food_products',
        'FROM tracker_food_duplicate_reviews630',
        'FROM coa_attachments',
        'FROM coa_default_documents645',
        'SELECT job_id,verify_code FROM coa_attachments',
        'multipart=True',
        'want_json=True',
        'accepted.json()["updated"] >= 1',
    ):
        assert marker in source, marker
    for forbidden in (
        "/opt/tracker/data/tracker.db",
        "TRACKER_CSRF_ENFORCE=0",
        "subprocess.run(",
        "os.system(",
        "requests.post(",
    ):
        assert forbidden not in source


def test_709_new_strict_browser_module_in_full_once_and_targeted_mode():
    text = RUNNER.read_text(encoding="utf-8")
    module = "tests/browser/test_csrf_food_coa709.py"
    assert text.count(module) == 2
    strict = text.index('echo "=== STRICT CSRF CORE TESTS PASSED ==="')
    targeted = text.index(
        'if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-positive709 ]]'
    )
    assert text[strict:targeted].count(module) == 1
    assert "STRICT_CSRF_709_FOOD_COA_TEN_POSITIVE_LIFECYCLES=PASSED" in text
    assert "TARGETED_CSRF_709_FOOD_COA_10_SIGNED_LIFECYCLES=PASSED" in text
    assert "TARGETED_CSRF_709_SCOPE=10_REAL_WRITES_NOT_FULL_CSRF_CLEARANCE" in text
    inventory = (
        ROOT / "tests/test_browser_qualification511.py"
    ).read_text(encoding="utf-8")
    assert '"tests/browser/test_csrf_food_coa709.py"' in inventory
    assert ('("csrf-positive709", '
            '"TARGETED_CSRF_709_FOOD_COA_10_SIGNED_LIFECYCLES=PASSED")') in inventory


def test_709_guarded_dev_only_runner_is_immutable_and_no_prod():
    worker = WORKER.read_text(encoding="utf-8")
    for marker in (
        "BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3",
        "REF=release/709-csrf-food-coa-positives",
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'git worktree add --detach "$QA" "$TARGET"',
        'git -C "$APP" worktree remove --force "$QA"',
        "tests/test_release709_csrf_food_coa.py",
        "tests/test_release708_csrf_remaining.py",
        "--targeted-strict csrf-positive709",
        "RELEASE_709_SOURCE=PASSED",
        "RELEASE_709_TARGETED_FOOD_COA_10=PASSED_NOT_GLOBAL_CLEARANCE",
        'readlink /proc/self/ns/net',
        'readlink /proc/1/ns/net',
    ):
        assert marker in worker, marker
    for forbidden in (
        "git push", "systemctl restart tracker", "/etc/tracker.env",
        "pip download", "pip install", "ssh ",
    ):
        assert forbidden not in worker


def test_709_food_fingerprint_uses_unique_namespaced_browser_group():
    # 709 originally used "QA709 distinct <scheme> <unique>", but the
    # production grouping algorithm compares only first two name words.
    # HTTP and HTTPS xdist workers could therefore merge distinct groups.
    from app.routers.food_duplicates629 import near_name_key641

    assert near_name_key641("QA709 distinct http abc") == near_name_key641(
        "QA709 distinct https xyz"
    )
    assert near_name_key641("QA709aaaaaaaaaa distinct http") != near_name_key641(
        "QA709bbbbbbbbbb distinct https"
    )
    source = BROWSER.read_text(encoding="utf-8")
    for action in ("merge", "resolve", "distinct", "editable"):
        assert f'name = "QA709" + unique + " {action} " + scheme' in source
    assert 'group = page.locator(' in source
    assert 'section.food629-group[aria-label="Duplicates of {name}"]' in source
    assert 'set(group.locator(".food629-meta-grid h3").all_inner_texts())' in source
    assert 'fingerprint = group.locator(' in source
    assert 'assert re.fullmatch(r"[a-f0-9]{64}", fingerprint)' in source
    assert "sha256(" not in source
    assert 'from hashlib import sha256' not in source
