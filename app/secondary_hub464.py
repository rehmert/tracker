"""Release 464: presentation-only secondary workspace hub.

This module never opens a database, chooses a user identity,
changes permissions or makes network requests.
"""
from html import escape

SECTIONS = (
    ("Food & Water", "/secondary/food",
     "/secondary/food/new", "food"),
    ("Vitals", "/secondary/vitals",
     "/secondary/vitals/new", "vitals"),
    ("Doses", "/secondary/doses",
     "/secondary/doses/new", "doses"),
    ("Inventory", "/secondary/inventory",
     "/secondary/inventory", "inventory"),
    ("Supplies", "/secondary/supplies",
     "/secondary/supplies", "supplies"),
    ("Reconstitution", "/secondary/reconstitution",
     "/secondary/reconstitution", "reconstitution"),
    ("Vial Reconciliation", "/secondary/reconcile",
     "/secondary/reconcile", "reconciliation"),
    ("Supply Use", "/secondary/supplies",
     "/secondary/supplies/use", "supply_use"),
)


def render_workspace_hub464(capabilities):
    """Render only allowlisted routes and boolean capabilities."""
    if (
        type(capabilities) is not dict
        or set(capabilities) != {
            section[3] for section in SECTIONS
        }
        or any(type(value) is not bool
               for value in capabilities.values())
    ):
        raise ValueError("Invalid workspace capabilities")

    cards = []

    for title, read_url, write_url, key in SECTIONS:
        enabled = capabilities[key]

        # These destinations are constants, never data
        # supplied by a browser or a secondary account.
        actions = (
            '<a class="hub-action464" href="'
            + escape(write_url, quote=True)
            + '">Open ' + escape(title) + '</a>'
            if enabled
            else '<span class="hub-disabled464">'
                 'Write action disabled</span>'
        )

        cards.append(
            '<article class="hub-card464" '
            'data-workspace-feature="' + key + '">'
            '<h3>' + escape(title) + '</h3>'
            '<p class="hub-status464">'
            + ('Logging enabled in DEV'
               if enabled else 'Read-only / disabled')
            + '</p>'
            '<div class="hub-actions464">'
            '<a href="' + escape(read_url, quote=True)
            + '">View</a>' + actions
            + '</div></article>'
        )

    return (
        '<section aria-labelledby="hub-title464">'
        '<h2 id="hub-title464">My Workspace</h2>'
        '<p>Choose a section to view your private records. '
        'Write actions appear only when their separate '
        'DEV feature gate is enabled.</p>'
        '<div class="hub-grid464">'
        + "".join(cards)
        + '</div></section>'
    )


HUB_STYLE464 = """
*{box-sizing:border-box}
body{margin:0;background:#f3f6fa;color:#182333;
font:16px/1.45 system-ui,sans-serif}
main{max-width:980px;margin:auto;padding:16px}
h1{font-size:1.7rem;margin:10px 0}
h2{font-size:1.25rem}
.hub-nav464{display:flex;flex-wrap:wrap;gap:10px;
margin:14px 0}
.hub-nav464 a{display:inline-flex;align-items:center;
padding:10px;min-height:44px;border-radius:8px;
background:#e2edf7;color:#164f85}
.hub-grid464{display:grid;grid-template-columns:1fr;gap:10px}
.hub-card464{padding:14px;border:1px solid #cad7e3;
border-radius:12px;background:white;min-width:0}
.hub-card464 h3{margin:0 0 8px;font-size:1.08rem}
.hub-status464{color:#405166;font-size:.9rem;margin:4px 0}
.hub-actions464{display:flex;flex-wrap:wrap;gap:8px;
margin-top:12px}
.hub-actions464 a{padding:10px 12px;border-radius:8px;
min-height:44px;display:inline-flex;align-items:center;
background:#e7f0fa;color:#174b78}
.hub-actions464 .hub-action464{background:#16558b;color:white}
.hub-disabled464{color:#566578;font-size:.85rem;
padding:10px 0}
.hub-data464{background:white;border:1px solid #cad7e3;
border-radius:12px;padding:14px;margin-top:16px;
overflow-x:auto}
.hub-data464 table{border-collapse:collapse;width:100%}
.hub-data464 th,.hub-data464 td{text-align:left;
padding:8px;border-bottom:1px solid #e0e7ed}
.hub-logout464 button{font:inherit;padding:12px 18px;
min-height:46px;background:#174b78;border:0;
color:white;border-radius:8px}
@media(min-width:650px){
.hub-grid464{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(min-width:950px){
.hub-grid464{grid-template-columns:repeat(3,minmax(0,1fr))}
}
"""


def render_workspace_nav464():
    return (
        '<nav class="hub-nav464" '
        'aria-label="Workspace navigation">'
        '<a href="/secondary/overview">Home</a>'
        '<a href="/secondary/food">Food</a>'
        '<a href="/secondary/vitals">Vitals</a>'
        '<a href="/secondary/doses">Doses</a>'
        '<a href="/secondary/inventory">Inventory</a>'
        '<a href="/secondary/supplies">Supplies</a>'
        '<a href="/secondary/readiness">Readiness</a>'
        '<a href="/secondary/security">Security</a>'
        '<a href="/secondary/account">My Account</a>'
        '<a href="/secondary/cutover">Cutover Readiness</a>'
        '<a href="/secondary/data-context">Data Context</a>'
        '<a href="/secondary/orm-summary">Private Summary</a>'
        '</nav>'
    )
