"""Release 453: pure, mobile-first weekly private nutrition rendering.

No database access, authentication changes, or write operations.
"""
from datetime import date, timedelta
from html import escape

NUTRIENTS = (
    ("energy", "Calories", "kcal"),
    ("proteins", "Protein", "g"),
    ("carbohydrates", "Carbs", "g"),
    ("fat", "Fat", "g"),
    ("fiber", "Fiber", "g"),
)


def format_value(value, unit=""):
    if value is None:
        return "—"
    return f"{float(value):,.1f}" + (f" {unit}" if unit else "")


def render_week453(reports, end_day):
    """Render seven already-authorized, isolated daily reports."""
    end = date.fromisoformat(end_day)
    if len(reports) != 7:
        raise ValueError("Expected seven daily reports")

    expected = [
        (end - timedelta(days=6 - i)).isoformat()
        for i in range(7)
    ]
    if [report["day"] for report in reports] != expected:
        raise ValueError("Weekly report date mismatch")

    summary = {}
    for key, _, _ in NUTRIENTS:
        complete_days = sum(
            report["coverage"][key] == len(report["items"])
            and not report["has_more"]
            for report in reports
        )
        reported_days = sum(
            report["coverage"][key] > 0 for report in reports
        )
        total = sum(report["totals"][key] for report in reports)
        summary[key] = (total, complete_days, reported_days)

    total_water = sum(report["water_oz"] for report in reports)
    water_target = sum(report["water_target_oz"] for report in reports)
    partial = any(report["has_more"] for report in reports)

    summary_html = []
    for key, label, unit in NUTRIENTS:
        total, complete, reported = summary[key]
        shown = format_value(total, unit) if reported else "—"
        summary_html.append(
            '<div class="tile"><span>' + escape(label)
            + '</span><strong>' + escape(shown)
            + '</strong><small>Reported on '
            + str(reported) + ' of 7 days'
            + ' · complete coverage on '
            + str(complete) + ' days</small></div>'
        )

    summary_html.append(
        '<div class="tile"><span>Water</span><strong>'
        + escape(format_value(total_water, "fl oz"))
        + '</strong><small>Seven-day target: '
        + escape(format_value(water_target, "fl oz"))
        + '</small></div>'
    )

    rows = []
    for report in reports:
        day = report["day"]
        nutrients = []
        for key, label, unit in NUTRIENTS[:4]:
            shown = (
                format_value(report["totals"][key], unit)
                if report["coverage"][key] else "—"
            )
            nutrients.append(
                '<span>' + escape(label) + ': '
                + '<b>' + escape(shown) + '</b></span>'
            )
        flag = (
            '<p class="warning">Partial day: more than 100 entries</p>'
            if report["has_more"] else ""
        )
        rows.append(
            '<article class="day-card"><header><a href="/secondary/food?day='
            + escape(day, quote=True) + '">'
            + escape(day) + '</a><span>'
            + str(len(report["items"])) + ' entries shown</span></header>'
            + '<div class="nutrients">' + "".join(nutrients) + '</div>'
            + '<p>Water: <b>'
            + escape(format_value(report["water_oz"], "fl oz"))
            + '</b></p>' + flag + '</article>'
        )

    previous = (end - timedelta(days=7)).isoformat() if end.toordinal() > 7 else None
    next_day = (end + timedelta(days=7)).isoformat() if end.toordinal() <= date.max.toordinal() - 7 else None

    prev_link = (
        '<a href="/secondary/food/week?day=' + previous
        + '">Previous 7 days</a>'
        if previous else ""
    )
    next_link = (
        '<a href="/secondary/food/week?day=' + next_day
        + '">Next 7 days</a>'
        if next_day else ""
    )
    warning = (
        "One or more days contain over 100 entries; totals exclude "
        "entries not shown."
        if partial else
        "Totals include recorded nutrient values only. Missing "
        "nutrients must not be interpreted as zero."
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Weekly Nutrition · Tracker</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#182333;
font:16px/1.45 system-ui,sans-serif}}
main{{max-width:850px;margin:auto;padding:16px}}
a{{color:#16558b}}
nav{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
nav a{{min-height:42px;display:inline-flex;align-items:center}}
h1{{font-size:1.55rem}}
h2{{font-size:1.15rem;margin-top:22px}}
.note{{font-size:.9rem;color:#405166}}
.stats{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.tile,.day-card{{background:white;border:1px solid #ccd7e2;
border-radius:12px;padding:12px;min-width:0}}
.tile span,.tile small{{display:block;color:#445569;font-size:.85rem}}
.tile strong{{display:block;font-size:1.35rem;overflow-wrap:anywhere}}
.tile small{{margin-top:5px}}
.days{{display:grid;gap:10px}}
.day-card header{{display:flex;gap:12px;flex-wrap:wrap;
justify-content:space-between}}
.day-card header span{{font-size:.85rem;color:#405166}}
.nutrients{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
gap:6px;margin:12px 0}}
.nutrients span{{font-size:.88rem}}
.warning{{color:#9b371b;font-weight:600}}
form{{display:flex;gap:10px;align-items:end;flex-wrap:wrap}}
label{{display:grid;gap:5px}}
input,button{{font:inherit;min-height:44px;padding:8px;border-radius:8px}}
button{{background:#16558b;color:white;border:0;padding:8px 14px}}
@media(min-width:680px){{
.stats{{grid-template-columns:repeat(3,minmax(0,1fr))}}
.days{{grid-template-columns:repeat(2,minmax(0,1fr))}}
}}
</style>
</head>
<body><main>
<nav aria-label="Secondary navigation">
<a href="/secondary/overview">Overview</a>
<a href="/secondary/food">Daily Journal</a>
<a href="/secondary/inventory">Inventory</a>
</nav>
<h1>Weekly Nutrition &amp; Water</h1>
<p class="note">Private workspace · Read-only</p>
<p>Reviewing {escape(expected[0])} through {escape(end_day)}</p>
<form action="/secondary/food/week" method="get">
<label>End date
<input type="date" name="day" value="{escape(end_day, quote=True)}" required>
</label>
<button type="submit">View Seven Days</button>
</form>
<nav aria-label="Weekly dates">
{prev_link}
<a href="/secondary/food/week">Current Week</a>
{next_link}
</nav>
<p><a href="/secondary/food/week.csv?day={escape(end_day, quote=True)}">Download Weekly CSV</a></p>
<h2>Seven-Day Totals</h2>
<div class="stats">{"".join(summary_html)}</div>
<p class="note">{escape(warning)}</p>
<h2>Daily Breakdown</h2>
<div class="days">{"".join(rows)}</div>
<p class="note">No secondary-user write permissions are added by this page.</p>
</main></body></html>'''
