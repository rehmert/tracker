"""Parse guarded release metadata without exposing sensitive log content."""
from pathlib import Path


def collect(root,limit=10):
    items=[]

    paths=sorted(
        Path(root).glob('release.*/deployment.log'),
        key=lambda p:p.stat().st_mtime,
        reverse=True
    )

    for path in paths[:limit]:
        started=None
        instance=None
        status='incomplete'

        for line in path.read_text(
            errors='replace'
        ).splitlines():
            if line.startswith('Started:'):
                parts=line.split(';')
                started=parts[0].removeprefix(
                    'Started:'
                ).strip()

                for part in parts[1:]:
                    if 'instance:' in part:
                        instance=part.split(
                            'instance:',1
                        )[1].strip()

            if line.startswith('EXIT_STATUS='):
                try:
                    code=int(line.split('=',1)[1])
                    status=(
                        'success' if code==0
                        else 'failed'
                    )
                except ValueError:
                    status='unknown'

        items.append({
            'started':started,
            'instance':instance,
            'status':status
        })

    return {
        'format':'tracker-release-history-v1',
        'entries':items
    }
