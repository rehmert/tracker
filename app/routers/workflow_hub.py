"""Read-only workflow hub. No database access or mutations."""
from fastapi import APIRouter, Request
from ..templating import render
router = APIRouter()
from ..navigation import directory_groups
@router.get("/workflow-hub")
def workflow_hub(request: Request):
    return render(request, "workflow_hub.html", groups=directory_groups())
