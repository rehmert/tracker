"""Release 705: read-only contract for the exact-commit full browser gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_705_full_browser_preview_is_guarded_and_noninstalling():
    source = (ROOT / "scripts/tracker-browser-preview705.sh").read_text()
    required = (
        'APP=/opt/tracker',
        'BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93',
        'REF=release/705-csrf-dependency-closeout',
        'INVOCATION_ID',
        'tracker-dev',
        'git branch --show-current',
        'git status --porcelain',
        'git rev-parse HEAD',
        'systemctl is-active --quiet tracker',
        'flock -n 9',
        'tracker705-browser-preview.lock',
        'RELEASE_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED',
        'VENDOR_SHA_BEFORE',
        'git fetch origin',
        'git merge-base --is-ancestor',
        'git diff --check',
        'git worktree add --detach',
        'bash scripts/tracker-release-scoped705.sh "$PY"',
        'git -C "$APP" worktree remove --force',
        'TRACKER_DATA_DIR="$RUN/test-data"',
        'bash scripts/tracker-browser-qualify.sh "$QA" "$PY"',
        'RELEASE_705_BROWSER_FULL=PASSED_DISPOSABLE_NO_INSTALL',
    )
    for marker in required:
        assert marker in source, marker
    assert source.index('bash scripts/tracker-release-scoped705.sh "$PY"') < source.index(
        'bash scripts/tracker-browser-qualify.sh "$QA" "$PY"'
    )
    assert source.index("RELEASE_705_SOURCE_REVALIDATED=PASSED") < source.index(
        "RELEASE_705_BROWSER_MODE=FULL_DISPOSABLE_HTTP_HTTPS_STRICT"
    )
    assert "tracker-db-sync.lock" not in source
    assert source.index("RELEASE_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED") < source.index(
        "RELEASE_705_BROWSER_FULL=PASSED_DISPOSABLE_NO_INSTALL"
    )
    for forbidden in (
        'systemctl restart', 'git reset', 'git push', 'pip install',
        'pip download', 'TRACKER_CSRF_ENFORCE=1', '/etc/tracker.env',
        'tracker-release.sh',
    ):
        assert forbidden not in source, forbidden


def test_705_full_browser_preview_is_allowed_by_exact_sha_source_gate():
    preview = (ROOT / "scripts/tracker-preview705.sh").read_text()
    assert 'scripts/tracker-browser-preview705.sh|\\' in preview
    assert 'tests/test_release705_runtime_preview.py|\\' in preview
    scoped = (ROOT / "scripts/tracker-release-scoped705.sh").read_text()
    assert 'bash -n scripts/tracker-browser-preview705.sh' in scoped
    assert 'tests/test_release705_runtime_preview.py' in scoped
    assert 'tests/browser/test_vitals_proxy_host522.py' in scoped
    assert 'tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification' in scoped
    assert scoped.index('RELEASE_705_BROWSER_RUNNER_CONTRACT=PASSED') < scoped.index(
        'RELEASE_705_ASGI_CSRF_NEGATIVE_CANARY=PASSED'
    )


def test_705_https_vitals_522_uses_shipped_edit_get_form():
    # A focused source-contract check that runs BEFORE the heavyweight
    # browser suite; full HTTPS create/edit/delete evidence still requires
    # executing tests/browser/test_vitals_proxy_host522.py on DEV.
    vitals = (ROOT / "app/templates/vitals.html").read_text()
    fixture = (ROOT / "tests/browser/test_vitals_proxy_host522.py").read_text()
    assert 'form method="get" action="/vitals/{{ r.id }}/edit"' in vitals
    assert 'name="days" value="{{ days }}"' in vitals
    assert 'name="events" value="{{ 1 if events_on else 0 }}"' in vitals
    assert "row.locator('form[method=\"get\"][action$=\"/edit\"]')" in fixture
    assert 'get_by_role("button", name="Edit", exact=True).click()' in fixture
    assert 'parse_qs(edit_url.query)' in fixture
    assert 'edit_url.scheme == "https"' in fixture
    assert 'edit_url.path == edit_path' in fixture
    assert "row.locator('a[href*=\"/edit\"]')" not in fixture


def test_705_vials_603_reports_navigation_opens_visible_disclosure():
    # Strict HTTP and HTTPS must use the actual Release 696 mobile Vials
    # disclosure; merely finding a hidden Reports anchor is not coverage.
    vials = (ROOT / "app/templates/vials.html").read_text()
    fixture = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    css = (ROOT / "app/static/css/tracker-integrated-flow696.css").read_text()
    assert '<details class="tracker-flow696-more">' in vials
    assert '<summary>More inventory tools</summary>' in vials
    assert '<a href="#tracker-inventory-reports">Reports</a>' in vials
    assert '.tracker-flow696-more > div > a' in css
    assert 'more = navigation.locator("details.tracker-flow696-more")' in fixture
    assert 'expect(more).not_to_have_attribute("open", "")' in fixture
    assert 'more.locator("summary").click()' in fixture
    assert 'expect(more).to_have_attribute("open", "")' in fixture
    assert 'expect(report_link).to_be_visible()' in fixture
    assert 'report_link.click()' in fixture
    assert 'expect(reports).to_have_attribute("open", "")' in fixture
    assert 'page.evaluate("location.hash")' in fixture
    assert 'navigation.locator(\'a[href="#tracker-inventory-reports"]\').click()' not in fixture
    assert "def test_603_vials_navigation_and_daily_action_filter(tab, scheme):" in fixture
