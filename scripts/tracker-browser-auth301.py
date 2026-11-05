#!/usr/bin/env python3
"""Run existing browser smoke tests with DEV Basic auth environment."""

import getpass
import os
import re
import shlex
import subprocess
import sys

from pathlib import Path


def credentials_from_files(paths):
    result={}

    for path in paths:
        path=Path(path)

        if not path.is_file():
            continue

        for line in path.read_text().splitlines():
            match=re.match(
                r'^\s*(?:export\s+)?(TRACKER_USER|TRACKER_PASS)\s*=\s*(.*)$',
                line
            )

            if not match:
                continue

            key,raw=match.groups()

            try:
                values=shlex.split(
                    raw,comments=True
                )
            except ValueError:
                continue

            if values:
                result[key]=values[0]

    return result


def main():
    if os.geteuid()!=0:
        raise SystemExit(
            'Run browser acceptance as root on tracker-dev'
        )

    values=credentials_from_files(
        ('/opt/tracker/.env','/etc/tracker.env')
    )

    username=(
        os.environ.get('TRACKER_TEST_USER')
        or values.get('TRACKER_USER')
        or ''
    )

    password=(
        os.environ.get('TRACKER_TEST_PASSWORD')
        or values.get('TRACKER_PASS')
        or ''
    )

    if not username or not password:
        if not sys.stdin.isatty():
            raise SystemExit(
                'Credentials missing; refusing unauthenticated browser gate'
            )

        if not username:
            username=input('DEV Tracker username: ')

        if not password:
            password=getpass.getpass(
                'DEV Tracker password: '
            )

    env=os.environ.copy()

    env['TRACKER_TEST_USER']=username
    env['TRACKER_TEST_PASSWORD']=password

    env['TRACKER_TEST_URL']=(
        env.get('TRACKER_TEST_URL')
        or 'http://127.0.0.1:8000'
    )

    command=[
        '/opt/tracker/.venv/bin/python',
        '-m','pytest','-q',
        '--tb=short','--maxfail=1',
        'tests/browser/test_pk_smoke_281.py'
    ]

    print(
        'Running authenticated read-only PK browser acceptance',
        flush=True
    )

    return subprocess.call(
        command,
        cwd='/opt/tracker',
        env=env
    )


if __name__=='__main__':
    raise SystemExit(main())
