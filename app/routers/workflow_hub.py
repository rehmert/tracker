"""Read-only workflow hub. No database access or mutations."""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
GROUPS = [('Daily workflow', [('Dashboard', '/'), ('Calendar', '/calendar'), ('Quick entry', '/quick-entry'), ('Dose log', '/doses'), ('Dose workspace', '/dose-workspace'), ('Activity timeline', '/activity')]), ('Protocols', [('Protocols', '/protocols'), ('Protocol tools', '/protocol-tools'), ('PK simulator', '/pk'), ('Blends', '/blends')]), ('Inventory and purchasing', [('Vials', '/vials'), ('Inventory health', '/inventory-health'), ('Inventory alerts', '/inventory-alerts'), ('Inventory timeline', '/inventory-timeline'), ('Inventory insights', '/inventory-intelligence'), ('Reconcile inventory', '/reconciliation'), ('Purchases', '/purchases'), ('Purchase analysis', '/purchase-analysis'), ('Vendor prices', '/vendor-prices'), ('Supplies', '/supplies'), ('COAs', '/coas')]), ('Health and records', [('Vitals', '/vitals'), ('Lab results', '/labs'), ('Health insights', '/health-insights'), ('Health timeline', '/health-timeline'), ('Health records', '/record-explorer/health'), ('Notes', '/pages'), ('Notes history', '/record-explorer/notes')]), ('Administration', [('Maintenance review', '/maintenance-review'), ('Data integrity', '/data-integrity'), ('Backups', '/backups'), ('Audit history', '/audit-history'), ('Reports', '/reports'), ('Exports', '/exports'), ('Database explorer', '/record-explorer/database')])]
@router.get("/workflow-hub")
def workflow_hub(request: Request):
    return templates.TemplateResponse(request, "workflow_hub.html", {"groups": GROUPS, "path": "/workflow-hub"})
