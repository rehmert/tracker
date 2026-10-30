from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from ..backup import create_backup, list_backups, prune_backups, verify_named_backup
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


@router.post('/backups/verify')
def backup_verify(name: str = Form(...)):
    from urllib.parse import quote
    try:
        manifest = verify_named_backup(name)
        count = len(manifest['files'])
        msg = f'Verified {name}: {count} files, checksums and SQLite integrity passed'
        return RedirectResponse('/backups?msg=' + quote(msg), status_code=303)
    except (OSError, ValueError, KeyError, TypeError, __import__('zipfile').BadZipFile, __import__('sqlite3').DatabaseError) as exc:
        return RedirectResponse('/backups?err=' + quote(f'Verification failed for {name}: {exc}'), status_code=303)
