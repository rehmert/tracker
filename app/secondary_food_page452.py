"""Release 452: mobile-first, escaped secondary food/day HTML rendering.

Pure formatting module. It has no database, authentication or write access.
"""
from datetime import date, timedelta
from html import escape
from .secondary_nutrients463 import MICROS


MACROS = (
    ("energy", "Calories", "kcal"),
    ("proteins", "Protein", "g"),
    ("carbohydrates", "Carbs", "g"),
    ("fat", "Fat", "g"),
    ("fiber", "Fiber", "g"),
)


def _num452(value, unit=""):
    if value is None:
        return "—"
    return f"{float(value):,.1f}" + (f" {unit}" if unit else "")


def render_food_day452(report):
    day = date.fromisoformat(report["day"])
    earlier = (day - timedelta(days=1)).isoformat() if day > date.min else None
    later = (day + timedelta(days=1)).isoformat() if day < date.max else None
    current = date.today().isoformat()

    day_label = escape(report["day"], quote=True)
    previous_link = (
        f'<a href="/secondary/food?day={earlier}">Previous day</a>'
        if earlier else ""
    )
    next_link = (
        f'<a href="/secondary/food?day={later}">Next day</a>'
        if later else ""
    )

    macro_cards = []
    for key, label, unit in MACROS:
        reported = report["coverage"][key]
        label_text = (
            "No reported values" if reported == 0 else
            f"Reported for {reported} of {len(report['items'])} shown entries"
        )
        value = _num452(
            report["totals"][key] if reported else None, unit
        )
        macro_cards.append(
            '<div class="stat"><span>'
            + escape(label) + '</span><strong>'
            + escape(value) + '</strong><small>'
            + escape(label_text) + "</small></div>"
        )

    micro_cards = []
    for key, label, unit in MICROS:
        reported = report["coverage"][key]
        value = _num452(
            report["totals"][key] if reported else None,
            unit,
        )
        micro_cards.append(
            '<div class="stat"><span>' + escape(label)
            + '</span><strong>' + escape(value)
            + '</strong><small>'
            + escape(
                f"Reported for {reported} of "
                f"{len(report['items'])} entries"
            )
            + '</small></div>'
        )

    food_cards = []
    for item in report["items"]:
        measurements = []
        for key, label, unit in MACROS[:4]:
            measurements.append(
                f'<span>{escape(label)}: <b>'
                + escape(_num452(item[key], unit))
                + "</b></span>"
            )
        food_cards.append(
            '<article class="food-card"><header><strong>'
            + escape(item["name"], quote=True)
            + '</strong><span class="meal">'
            + escape(item["meal"], quote=True)
            + '</span></header><p>'
            + escape(_num452(item["servings"]))
            + ' serving(s)</p><div class="nutrients">'
            + "".join(measurements) + "</div></article>"
        )
    if not food_cards:
        food_cards.append(
            '<p class="empty">No food entries recorded for this day.</p>'
        )

    count_note = (
        "Showing the 100 newest food entries only. Nutrient totals "
        "include these displayed entries, not older entries from the day."
        if report["has_more"]
        else "Totals are based on recorded nutrient values only; "
             "unknown nutrients are not treated as confirmed zero."
    )
    water = _num452(report["water_oz"], "fl oz")
    water_target = _num452(report["water_target_oz"], "fl oz")

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Food &amp; Water · Tracker</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#182333;font:16px/1.45 system-ui,sans-serif}}
main{{max-width:840px;margin:auto;padding:16px}}
nav{{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}}
nav a{{color:#164f85;min-height:40px;display:inline-flex;align-items:center}}
h1{{font-size:1.6rem;margin:.4rem 0}}
h2{{font-size:1.15rem;margin:1.1rem 0 .5rem}}
p{{margin:.55rem 0}}
.note{{color:#405166;font-size:.9rem}}
.day-picker{{display:flex;gap:10px;flex-wrap:wrap;align-items:end}}
.day-picker label{{display:grid;gap:4px;flex:1;min-width:170px}}
.day-picker input,.day-picker button{{font:inherit;min-height:44px;padding:8px;border-radius:7px}}
.day-picker button{{background:#164f85;color:#fff;border:0;cursor:pointer}}
.stats{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.stat,.food-card,.panel{{background:#fff;border:1px solid #cdd7e2;border-radius:12px;padding:12px}}
.stat span,.stat small{{display:block;color:#445569;font-size:.85rem}}
.stat strong{{display:block;font-size:1.45rem;font-variant-numeric:tabular-nums}}
.stat small{{line-height:1.25;margin-top:4px}}
.food-list{{display:grid;gap:10px}}
.food-card header{{display:flex;justify-content:space-between;gap:10px;align-items:baseline}}
.food-card .meal{{font-size:.85rem;color:#46586b}}
.food-card p{{color:#415163;font-size:.9rem}}
.nutrients{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}}
.nutrients span{{font-size:.88rem}}
.empty{{padding:16px;background:#fff;border-radius:10px}}
.micro-details463{{
background:#fff;border:1px solid #cdd7e2;
border-radius:12px;padding:12px;margin:16px 0
}}
.micro-details463 summary{{
min-height:44px;padding:8px 0;
cursor:pointer;font-weight:700
}}
@media(min-width:680px){{
.stats{{grid-template-columns:repeat(5,minmax(0,1fr))}}
.food-list{{grid-template-columns:repeat(2,minmax(0,1fr))}}
}}
</style>
</head>
<body>
<main>
<nav aria-label="Secondary workspace navigation">
<a href="/secondary/overview">Overview</a>
<a href="/secondary/vitals">Vitals</a>
<a href="/secondary/doses">Doses</a>
<a href="/secondary/inventory">Inventory</a>
<a href="/secondary/supplies">Supplies</a>
<a href="/secondary/readiness">Readiness</a>
<a href="/secondary/security">Security</a>
</nav>
<h1>Food &amp; Water</h1>
<p><a href="/secondary/food/new">Log Food or Water</a></p>
<p><a href="/secondary/food/week?day={day_label}">View Seven-Day Nutrition &amp; Water Review</a></p>
<p class="note">Private workspace</p>
<form method="get" action="/secondary/food" class="day-picker">
<label>Journal day
<input name="day" type="date" required value="{day_label}">
</label>
<button type="submit">View Day</button>
</form>
<nav aria-label="Food journal dates">
{previous_link}
<a href="/secondary/food?day={current}">Today</a>
{next_link}
</nav>
<h2>Nutrition for {day_label}</h2>
<div class="stats">{"".join(macro_cards)}</div>
<p class="note">{escape(count_note)}</p>
<details class="micro-details463">
<summary>Micronutrients and Other Nutrients</summary>
<div class="stats">{"".join(micro_cards)}</div>
<p class="note">Unknown is not zero.
Totals include displayed entries only.</p>
</details>
<h2>Water</h2>
<div class="panel"><strong>{escape(water)}</strong>
<span class="note"> logged · target {escape(water_target)}</span></div>
<h2>Food entries</h2>
<div class="food-list">{"".join(food_cards)}</div>
<p class="note">Private journal history only. Recording and editing food
for secondary accounts will require a separately reviewed write gate.</p>
</main>
</body>
</html>'''
