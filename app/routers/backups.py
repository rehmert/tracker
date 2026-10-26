from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from ..backup import create_backup, list_backups, prune_backups
from ..templating import render

router = APIRouter()


@router.get('/backups')
def backup_page(request: Request, msg: str = '', err: str = ''):
    return render(request, 'backups.html', backups=list_backups(), msg=msg, err=err)


@router.post('/backups/create')
def backup_create():
    try:
        archive = create_backup()
        prune_backups()
        return RedirectResponse('/backups?msg=Backup+created+and+verified', status_code=303)
    except (OSError, ValueError) as exc:
        from urllib.parse import quote
        return RedirectResponse('/backups?err=' + quote(str(exc)), status_code=303)
