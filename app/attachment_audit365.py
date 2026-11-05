"""Read-only attachment health report. Never deletes an unreferenced file."""
import argparse
import json
from pathlib import Path
from .backup_references341 import required_attachments
from . import config


def audit_uploads(data_dir):
    root=Path(data_dir).resolve()
    db=root/'tracker.db'
    if not db.is_file():
        raise FileNotFoundError(f'Database not found: {db}')
    required=required_attachments(db)
    uploads=root/'uploads'
    found=set()
    unsafe=[]
    if uploads.is_symlink():
        return {
            'required_count':len(required),
            'present_count':0,
            'missing':sorted(required),
            'unreferenced_candidates':[],
            'unsafe_entries':['uploads'],
        }
    for folder in ('coa','labs'):
        directory=uploads/folder
        if directory.is_symlink():
            unsafe.append(f'uploads/{folder}')
            continue
        if not directory.exists():
            continue
        if not directory.is_dir():
            unsafe.append(f'uploads/{folder}')
            continue
        for child in sorted(directory.iterdir()):
            name=f'uploads/{folder}/{child.name}'
            if child.is_symlink() or not child.is_file():
                unsafe.append(name)
            else:
                found.add(name)
    return {
        'required_count':len(required),
        'present_count':len(found),
        'missing':sorted(required-found),
        'unreferenced_candidates':sorted(found-required),
        'unsafe_entries':sorted(unsafe),
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default=str(config.DATA_DIR))
    args=parser.parse_args(argv)
    report=audit_uploads(args.data_dir)
    print(json.dumps(report,indent=2,sort_keys=True))
    return 2 if report['missing'] or report['unsafe_entries'] else 0


if __name__=='__main__':
    raise SystemExit(main())
