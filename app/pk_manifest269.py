"""Read-only release evidence without exposing logs or file paths."""
import json
from pathlib import Path
from .pk_release_report253 import collect


def report(root):
    data=collect(root,limit=20)
    entries=data['entries']

    return {
        'format':'tracker-release-manifest-v1',
        'count':len(entries),
        'successes':sum(
            e['status']=='success'
            for e in entries
        ),
        'failures':sum(
            e['status']=='failed'
            for e in entries
        ),
        'incomplete':sum(
            e['status']=='incomplete'
            for e in entries
        ),
        'entries':entries
    }


def write_atomic(root,destination):
    root=Path(root)
    destination=Path(destination)

    # The privileged local CLI selects the destination.
    content=json.dumps(
        report(root),
        indent=2,
        sort_keys=True
    )+'\n'

    temp=destination.with_name(
        destination.name+'.tmp'
    )

    temp.write_text(content)
    temp.chmod(0o600)
    temp.replace(destination)
    destination.chmod(0o600)

    return destination
