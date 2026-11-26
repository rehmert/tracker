"""Canonical navigation registry. Stable group keys preserve browser preferences.
Every historical URL remains searchable; focused navigation is a presentation choice.
"""
NAVIGATION = (
    ("Today", "Home", (
        ("/mobile", "Today", True),
        ("/activity", "Daily activity", False),
        ("/pages", "Notes", True),
        ("/quick-entry", "Quick entry", False),
        ("/workflow-hub", "Workflow hub", False),
        ("/record-explorer/notes", "Notes history", False),
    )),
    ("Calendar & Dosing", "Schedule", (
        ("/calendar", "Calendar", True),
        ("/protocols", "Protocols", True),
        ("/regimen", "Medications & supplements", True),
        ("/doses", "Administrations", True),
        ("/dose-workspace", "Dose Workspace", False),
        ("/protocol-tools", "Protocol tools", False),
        ("/protocol-coverage", "Protocol coverage", False),
        ("/pk", "PK Simulator", False),
    )),
    ("Nutrition", "Nutrition", (
        ("/food", "Food Journal", True),
    )),
    ("Workouts", "Workouts", (
        ("/workouts", "Workouts", True),
    )),
    ("Health", "Health", (
        ("/progress", "Progress", True),
        ("/vitals", "Vitals", True),
        ("/labs", "Lab results", True),
        ("/health-timeline", "Health timeline", False),
        ("/health-insights", "Health insights", False),
        ("/record-explorer/health", "Health records", False),
        ("/reports", "Reports", False),
    )),
    ("Inventory", "Inventory", (
        ("/vials", "Stock", True),
        ("/purchases", "Purchases", True),
        ("/planning-hub", "Forecast & planning", True),
        ("/coas", "Certificates (COAs)", True),
        ("/inventory-health", "Inventory issues", True),
        ("/blends", "Blends", False),
        ("/supplies", "Supplies", False),
        ("/compounds", "Compounds", False),
        ("/vendor-prices", "Vendor prices", False),
        ("/replenishment-review", "Replenishment review", False),
        ("/inventory-intelligence", "Inventory insights", False),
        ("/inventory-alerts", "Inventory alerts", False),
        ("/inventory-forecast", "Inventory forecast", False),
        ("/forecast-horizons", "Forecast horizons", False),
        ("/forecast-audit", "Forecast audit", False),
        ("/scheduled-forecast", "Scheduled forecast", False),
        ("/expiry-exposure", "Expiry exposure", False),
        ("/fefo-forecast", "FEFO forecast", False),
        ("/inventory-timeline", "Inventory timeline", False),
        ("/reconciliation", "Reconcile inventory", False),
        ("/record-explorer/vials", "Record explorer", False),
        ("/purchase-analysis", "Purchase analytics", False),
        ("/consumption", "Consumption", False),
        ("/reconstitution-calculator", "Reconstitution calculator", False),
    )),
    ("Manage", "Settings", (
        ("/integrations/google-tasks", "Google Tasks", True),
        ("/data-quality", "Data Quality", True),
        ("/exports", "Exports", False),
        ("/backups", "Backups", False),
        ("/audit-history", "Audit history", False),
        ("/maintenance-review", "Maintenance review", False),
        ("/data-integrity", "Data integrity", False),
        ("/sqlite-viewer", "SQLite viewer", False),
        ("/record-explorer/database", "Database explorer", False),
    )),
)


def current_navigation(path):
    """Only the longest matching destination is current; never match siblings."""
    paths = [href for _, _, links in NAVIGATION for href, _, _ in links]
    if path == "/":
        return "/"
    return max((href for href in paths if path == href or path.startswith(href + "/")), key=len, default=None)


def directory_groups():
    return [(title, [(label, href) for href, label, _ in links]) for _, title, links in NAVIGATION]
