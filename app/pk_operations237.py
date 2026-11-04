"""Read-only SQLite integrity summary, without exposing deployment logs."""
from sqlalchemy import text
from .pk_operational221 import status


def health(db):
    info=status()
    if db.bind.dialect.name!='sqlite':
        info['database_check']='unsupported'
    else:
        result=db.execute(text('PRAGMA quick_check(1)')).scalar()
        info['database_check']='ok' if result=='ok' else 'requires_attention'
    info['read_only']=True
    info['backup_validation']='Use root-only guarded release verification logs'
    return info
