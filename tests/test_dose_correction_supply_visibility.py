"""Make original disposable usage visible when correcting a dose."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def supplies_fragment():
    source = HTML.read_text()
    marker = '<details class="wide" {% if used %}open{% endif %}>'

    assert source.count(marker) == 1

    start = source.index(marker)
    end = source.index("</details>", start) + len("</details>")

    return source[start:end]


def render_supplies(supplies, used, counted=None):
    env = Environment(autoescape=True)
    env.filters["num"] = lambda x: f"{x:g}"

    return env.from_string(supplies_fragment()).render(
        supplies=supplies,
        used=used,
        counted_supply_kinds=counted or {"syringe", "needle"},
    )


def supply(sid, name, remaining, kind="syringe"):
    return SimpleNamespace(
        id=sid,
        name=name,
        remaining_qty=remaining,
        kind=kind,
    )


def test_original_usage_expands_the_section():
    html = render_supplies(
        [supply(10, "Syringe", 4)],
        {10: 2},
    )

    assert '<details class="wide" open>' in html
    assert "1 previously selected" in html
    assert "originally recorded" in html
    assert 'class="dose-correction-original"' in html
    assert 'value="2"' in html
    assert "6 available" in html


def test_multiple_original_supply_types_are_counted():
    html = render_supplies(
        [
            supply(10, "Syringe", 4),
            supply(11, "Needle", 0, "needle"),
        ],
        {10: 2, 11: 1},
    )

    assert "2 previously selected" in html
    assert html.count(
        'class="dose-correction-original"'
    ) == 2
    assert "1 available" in html


def test_no_original_usage_starts_collapsed():
    html = render_supplies(
        [supply(10, "Syringe", 4)],
        {},
    )

    assert '<details class="wide" >' in html
    assert "previously selected" not in html
    assert "originally recorded" not in html
    assert 'class="dose-correction-original"' not in html


def test_no_supplies_shows_useful_empty_state():
    html = render_supplies([], {})

    assert (
        "No available or previously recorded supplies for this dose."
        in html
    )
    assert 'colspan="4"' in html


def test_existing_supply_entry_contracts_preserved():
    source = HTML.read_text()

    required = (
        'name="supply_id_used"',
        'name="supply_qty_{{ s.id }}"',
        'value="{{ used.get(s.id,1) }}"',
        'data-counted="',
        's.remaining_qty + used.get(s.id, 0)',
        '<th>Available for correction</th>',
        '<section class="card wide" aria-label="Change history">',
    )

    for marker in required:
        assert marker in source, marker

    Environment().parse(source)


def test_correction_backend_remains_authoritative():
    source = ROUTER.read_text()

    post = source.split(
        '@router.post("/doses/{did}/edit")', 1
    )[1].split(
        '@router.get("/dose-workspace")', 1
    )[0]

    assert "reserve_inventory_write" in post
    assert "manual_supplies.selections(" in post
    assert "credits={u.supply_id:u.amount" in post
    assert 'action="edit"' in post
    assert "db.commit()" in post
