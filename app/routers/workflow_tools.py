
"""Tracker Release 69-72: read-only workflow tools."""

import html
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Protocol,
    ProtocolRevision,
    Purchase,
    Vial,
    Supply,
)

router = APIRouter()


def esc(value):
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def link(path, label):
    return f'<a href="{esc(path)}">{esc(label)}</a>'


def page(title, body):
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Tracker</title>
<style>
:root {{
  color-scheme:light dark;
  font-family:system-ui,sans-serif;
}}
body {{
  max-width:1250px;
  margin:2rem auto;
  padding:0 1rem;
  line-height:1.5;
}}
nav {{
  margin-bottom:2rem;
}}
a {{
  color:inherit;
  text-decoration:underline;
}}
table {{
  width:100%;
  border-collapse:collapse;
}}
th,td {{
  text-align:left;
  padding:.7rem;
  border-bottom:1px solid #8885;
  vertical-align:top;
}}
th {{
  background:#8882;
}}
pre {{
  white-space:pre-wrap;
  overflow-wrap:anywhere;
  margin:0;
}}
.card {{
  border:1px solid #8885;
  border-radius:12px;
  padding:1rem;
  margin:1rem 0;
}}
small {{
  opacity:.75;
}}
input,select,button {{
  font:inherit;
  padding:.4rem;
}}
.scroll {{
  overflow-x:auto;
}}
</style>
</head>
<body>
<nav>
{link("/", "Dashboard")} ·
{link("/protocols", "Protocols")} ·
{link("/purchases", "Purchases")} ·
{link("/protocol-tools", "Protocol tools")} ·
{link("/purchase-analysis", "Purchasing analytics")}
</nav>
<main>
<h1>{esc(title)}</h1>
{body}
</main>
</body>
</html>""")


def revisions_for(db, pid):
    return list(db.scalars(
        select(ProtocolRevision)
        .where(ProtocolRevision.protocol_id == pid)
        .order_by(ProtocolRevision.revision.desc())
    ))


def snapshot(revision):
    try:
        data = json.loads(revision.snapshot_json)
    except (ValueError, TypeError):
        raise HTTPException(
            422,
            "Invalid saved protocol revision JSON",
        )
    if not isinstance(data, dict):
        raise HTTPException(
            422,
            "Protocol revision must be a JSON object",
        )
    return data


def flatten(value, prefix=""):
    result = {}

    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten(value[key], path))

    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(
                flatten(item, f"{prefix}[{index}]")
            )

    else:
        result[prefix] = value

    return result


@router.get("/protocol-tools")
def protocol_tools(db: Session = Depends(get_db)):
    protocols = list(db.scalars(
        select(Protocol).order_by(Protocol.name)
    ))

    counts = defaultdict(int)

    for pid, in db.execute(
        select(ProtocolRevision.protocol_id)
    ):
        counts[pid] += 1

    rows = []

    for p in protocols:
        actions = [
            link(
                f"/protocol-tools/{p.id}/compare",
                "Compare revisions",
            ),
            link(
                f"/protocol-tools/{p.id}/template.json",
                "Export latest saved revision",
            ),
            link(
                f"/protocols/{p.id}",
                "Open protocol",
            ),
        ]

        rows.append(
            "<tr>"
            f"<td>{esc(p.name)}</td>"
            f"<td>{'Active' if p.is_active else 'Inactive'}</td>"
            f"<td>{counts[p.id]}</td>"
            f"<td>{' · '.join(actions)}</td>"
            "</tr>"
        )

    body = """
<p>Compare historical protocol configurations and export
the latest saved revision as JSON.</p>
<p><small>These tools do not modify active protocols.</small></p>
<div class="scroll">
<table>
<thead>
<tr>
<th>Protocol</th><th>Status</th>
<th>Revisions</th><th>Actions</th>
</tr>
</thead>
<tbody>
""" + "".join(rows) + """
</tbody></table></div>
"""

    if not rows:
        body += "<p>No protocols found.</p>"

    return page("Protocol tools", body)


@router.get("/protocol-tools/{pid}/compare")
def compare_protocol(
    pid: int,
    left: int = 0,
    right: int = 0,
    db: Session = Depends(get_db),
):
    protocol = db.get(Protocol, pid)

    if protocol is None:
        raise HTTPException(404, "Protocol not found")

    revisions = revisions_for(db, pid)

    if not revisions:
        return page(
            "Protocol comparison",
            "<p>No saved revisions are available.</p>"
            + link("/protocol-tools", "Back"),
        )

    by_number = {
        r.revision: r for r in revisions
    }

    if left == 0:
        left = revisions[
            1 if len(revisions) > 1 else 0
        ].revision

    if right == 0:
        right = revisions[0].revision

    if left not in by_number or right not in by_number:
        raise HTTPException(
            404,
            "Selected revision not found",
        )

    before = flatten(snapshot(by_number[left]))
    after = flatten(snapshot(by_number[right]))

    missing = object()
    differences = []

    for field in sorted(set(before) | set(after)):
        old = before.get(field, missing)
        new = after.get(field, missing)

        if old != new:
            def display(value):
                if value is missing:
                    return "(not present)"
                return json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                )

            differences.append(
                "<tr>"
                f"<td><code>{esc(field)}</code></td>"
                f"<td><pre>{esc(display(old))}</pre></td>"
                f"<td><pre>{esc(display(new))}</pre></td>"
                "</tr>"
            )

    options = []

    for r in revisions:
        options.append(
            f'<option value="{r.revision}">'
            f'Revision {r.revision}</option>'
        )

    def select(name, selected):
        return (
            f'<select name="{name}">'
            + "".join(
                f'<option value="{r.revision}"'
                + (
                    " selected"
                    if r.revision == selected
                    else ""
                )
                + f'>Revision {r.revision}</option>'
                for r in revisions
            )
            + "</select>"
        )

    form = f"""
<form method="get">
<label>Earlier revision:
{select("left", left)}</label>
<label>Later revision:
{select("right", right)}</label>
<button type="submit">Compare</button>
</form>
"""

    body = (
        link("/protocol-tools", "Back to protocol tools")
        + f"<p>Protocol: <strong>{esc(protocol.name)}</strong></p>"
        + form
        + f"<h2>{len(differences)} changed fields</h2>"
        + '<div class="scroll"><table>'
        + "<thead><tr>"
        + "<th>Field</th><th>Earlier</th><th>Later</th>"
        + "</tr></thead><tbody>"
        + "".join(differences)
        + "</tbody></table></div>"
        + "<p><small>Array elements are compared by position. "
        + "Reordering may appear as multiple changes.</small></p>"
    )

    return page("Protocol revision comparison", body)


@router.get("/protocol-tools/{pid}/template.json")
def export_protocol_template(
    pid: int,
    db: Session = Depends(get_db),
):
    protocol = db.get(Protocol, pid)

    if protocol is None:
        raise HTTPException(404, "Protocol not found")

    revisions = revisions_for(db, pid)

    if not revisions:
        raise HTTPException(
            404,
            "No saved revision available for export",
        )

    latest = revisions[0]

    data = {
        "format": "tracker-protocol-snapshot",
        "format_version": 1,
        "protocol_id": protocol.id,
        "protocol_name": protocol.name,
        "revision": latest.revision,
        "saved_at": (
            latest.created_at.isoformat()
            if latest.created_at else None
        ),
        "snapshot": snapshot(latest),
    }

    return JSONResponse(
        data,
        headers={
            "Content-Disposition":
            f'attachment; filename="protocol-{pid}-revision-{latest.revision}.json"'
        },
    )


def money(cents):
    return f"${cents / 100:,.2f}"


@router.get("/purchase-analysis")
def purchase_analysis(db: Session = Depends(get_db)):
    purchases = list(db.scalars(
        select(Purchase).order_by(
            Purchase.purchased_on.desc(),
            Purchase.id.desc(),
        )
    ))

    vials = list(db.scalars(select(Vial)))
    supplies = list(db.scalars(select(Supply)))

    by_purchase_vials = defaultdict(list)
    by_purchase_supplies = defaultdict(list)

    for vial in vials:
        if vial.purchase_id is not None:
            by_purchase_vials[vial.purchase_id].append(vial)

    for supply in supplies:
        if supply.purchase_id is not None:
            by_purchase_supplies[supply.purchase_id].append(supply)

    vendor_stats = defaultdict(
        lambda: {
            "orders": 0,
            "vials": 0,
            "supplies": 0,
            "known_cost_cents": 0,
        }
    )

    rows = []
    overall_known = 0

    for p in purchases:
        pv = by_purchase_vials[p.id]
        ps = by_purchase_supplies[p.id]

        vial_cost = sum(
            v.unit_price_cents or 0
            for v in pv
        )

        supply_cost = 0

        for s in ps:
            if s.bulk_total_cents is not None:
                supply_cost += s.bulk_total_cents

            elif (
                s.unit_price_cents is not None
                and s.purchased_qty is not None
            ):
                supply_cost += round(
                    s.unit_price_cents * s.purchased_qty
                )

        adjustments = (
            (p.shipping_cents or 0)
            + (p.tax_cents or 0)
            - (p.discount_cents or 0)
        )

        known = vial_cost + supply_cost + adjustments
        overall_known += known

        vendor = p.vendor or "Unspecified"

        stats = vendor_stats[vendor]
        stats["orders"] += 1
        stats["vials"] += len(pv)
        stats["supplies"] += len(ps)
        stats["known_cost_cents"] += known

        rows.append(
            "<tr>"
            f"<td>{esc(p.purchased_on)}</td>"
            f"<td>{esc(vendor)}</td>"
            f"<td>{esc(p.order_ref)}</td>"
            f"<td>{len(pv)}</td>"
            f"<td>{len(ps)}</td>"
            f"<td>{money(known)}</td>"
            f"<td>{link('/purchases/' + str(p.id), 'View')}</td>"
            "</tr>"
        )

    vendor_rows = []

    for vendor, stats in sorted(
        vendor_stats.items(),
        key=lambda pair: (
            -pair[1]["orders"],
            pair[0].lower(),
        ),
    ):
        vendor_rows.append(
            "<tr>"
            f"<td>{esc(vendor)}</td>"
            f"<td>{stats['orders']}</td>"
            f"<td>{stats['vials']}</td>"
            f"<td>{stats['supplies']}</td>"
            f"<td>{money(stats['known_cost_cents'])}</td>"
            "</tr>"
        )

    body = f"""
<div class="card">
<h2>Recorded purchasing summary</h2>
<p>
<strong>{len(purchases)}</strong> purchase records ·
<strong>{len(vials)}</strong> vial records ·
<strong>{len(supplies)}</strong> supply records
</p>
<p>
Known recorded cost components:
<strong>{money(overall_known)}</strong>
</p>
<p><small>
This is not necessarily total spending. Missing item prices
are treated as unknown, not verified zero cost. Vial and
supply prices are summed using their stored values;
shipping, tax, and discounts are applied separately.
</small></p>
</div>

<h2>Vendor summary</h2>
<div class="scroll"><table>
<thead><tr>
<th>Vendor</th><th>Orders</th>
<th>Vials</th><th>Supplies</th><th>Known costs</th>
</tr></thead>
<tbody>
{''.join(vendor_rows)}
</tbody></table></div>

<h2>Purchase history</h2>
<div class="scroll"><table>
<thead><tr>
<th>Date</th><th>Vendor</th><th>Reference</th>
<th>Vials</th><th>Supplies</th>
<th>Known costs</th><th>Details</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody></table></div>

<p>
{link("/reconciliation", "Inventory reconciliation")}
·
{link("/inventory-intelligence", "Inventory intelligence")}
·
{link("/vendor-prices", "Vendor prices")}
</p>
"""

    return page("Purchasing analytics", body)
