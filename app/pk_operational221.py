"""Nonsecret, read-only running-code identity metadata."""
from pathlib import Path
from subprocess import run


def status(root=Path('/opt/tracker')):
    try:
        r=run(
            [
                'git','-C',str(root),
                'rev-parse','--verify','HEAD'
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )

        commit=r.stdout.strip()

        if (
            r.returncode
            or len(commit)!=40
            or any(
                c not in '0123456789abcdef'
                for c in commit
            )
        ):
            commit=None

    except (OSError,TimeoutError):
        commit=None

    return {
        'code_commit':commit,
        'database_migrations_included':False,
        'operational_note':(
            'Deployment status and backup restore '
            'proof remain in server-side guarded release logs.'
        )
    }
