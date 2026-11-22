#!/usr/bin/env python3
"""DEV-only full backend parity against pristine Release 750.

Run EVERY backend test on both exact base and candidate; fail if candidate
loses coverage, adds skips/errors/failures, or if either runner fails abnormally.
Legacy failures are retained in private local reports, never declared passed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

APP = Path('/opt/tracker')
IGNORES = (
    'tests/browser',
    'tests/test_bulk_vial_browser.py',
    'tests/test_bulk_vial_guided_browser.py',
    'tests/test_bulk_delete_browser.py',
    'tests/test_purchase_vial_browser.py',
    'tests/test_stage33_browser_sorting.py',
    'tests/test_health_timeline_dates_browser.py',
    'tests/test_vitals_csv_browser.py',
)


class ParityError(RuntimeError):
    pass


def git(*args: str) -> str:
    return subprocess.check_output(
        ['git', '-c', f'safe.directory={APP}', '-C', str(APP), *args],
        text=True, stderr=subprocess.DEVNULL,
    ).strip()


def read_report(path: Path) -> dict:
    root = ET.parse(path).getroot()
    cases = root.findall('.//testcase')
    if not cases:
        raise ParityError('Empty JUnit report; release blocked')
    result = {}
    for case in cases:
        # JUnit classname/name are not guaranteed unique. A pinned pytest
        # plugin records the exact collection nodeid for BOTH source trees.
        evidence = [prop.get('value') for prop in
                    case.findall('./properties/property')
                    if prop.get('name') == 'tracker_pytest_nodeid_751']
        if len(evidence) != 1:
            raise ParityError('Missing or duplicate pytest nodeid property')
        nodeid = evidence[0]
        if not nodeid or not nodeid.startswith('tests/') or nodeid in result:
            raise ParityError('Missing or duplicate pytest nodeid')
        result[nodeid] = ('error' if case.find('error') is not None else
                            'failed' if case.find('failure') is not None else
                            'skipped' if case.find('skipped') is not None else
                            'passed')
    return result


def compare_reports(base: dict, candidate: dict) -> dict:
    base_ids, candidate_ids = set(base), set(candidate)
    missing = base_ids - candidate_ids
    new_skips = {key for key, outcome in candidate.items()
                 if outcome == 'skipped' and base.get(key) != 'skipped'}
    new_failures = {key for key, outcome in candidate.items()
                    if outcome in ('failed', 'error')
                    and base.get(key) != outcome}
    if missing or new_skips or new_failures:
        # Publish only bounded, filename-only diagnostics. Test names,
        # JUnit XML, patient fixtures and raw tracebacks stay private.
        import re
        abnormal = missing | new_skips | new_failures
        filenames = set()
        for nodeid in abnormal:
            # Only publish safe relative source filenames, never full nodeids,
            # assertion payloads, JUnit, logs or private test data.
            match = re.match(
                r'^(tests/(?:[A-Za-z0-9_]+/)*test_[A-Za-z0-9_]+[.]py)(?:::|$)',
                nodeid,
            )
            if match:
                filenames.add(match.group(1))
        for filename in sorted(filenames)[:12]:
            print('FAILED ' + filename, file=sys.stderr)
        raise ParityError(
            'Backend baseline parity failed: '
            f'missing={len(missing)} new_skips={len(new_skips)} '
            f'new_failures={len(new_failures)}; inspect private JUnit reports'
        )
    inherited = sum(v in ('failed', 'error') for v in candidate.values())
    return {'baseline_cases': len(base), 'candidate_cases': len(candidate),
            'inherited_failures': inherited}


def run_suite(python: str, source: Path, data: Path, output: Path,
              plugin_dir: Path) -> None:
    data.mkdir(mode=0o700)
    env = dict(os.environ, TRACKER_DATA_DIR=str(data),
               # Source first; shared pinned plugin loaded from candidate.
               PYTHONPATH=os.pathsep.join((str(source), str(plugin_dir))),
               PYTHONDONTWRITEBYTECODE='1')
    argv = [python, '-B', '-m', 'pytest', '-p', 'tracker_pytest_nodeid751',
            '-q', '--tb=short',
            '--disable-warnings', '-n', '16', '--dist=loadfile',
            '--durations=20', 'tests']
    argv += [f'--ignore={path}' for path in IGNORES]
    argv += [f'--junitxml={output}.xml']
    with (output.with_suffix('.log')).open('wb') as log:
        os.chmod(log.name, 0o600)
        try:
            result = subprocess.run(argv, cwd=source, env=env,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, timeout=1200,
                                    check=False)
        except subprocess.TimeoutExpired as exc:
            raise ParityError('Backend full suite exceeded 1200s') from exc
    if result.returncode not in (0, 1):
        raise ParityError(f'Backend suite incomplete: exit {result.returncode}')
    if not (output.with_suffix('.xml')).is_file():
        raise ParityError('Missing backend JUnit evidence')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or os.uname().nodename.split('.')[0] != 'tracker-dev':
        raise ParityError('DEV root only')
    candidate = args.candidate.resolve()
    if (git('branch', '--show-current') != 'main'
            or git('rev-parse', 'HEAD') != args.base
            or git('status', '--porcelain')):
        raise ParityError('Installed DEV baseline not pristine')
    if subprocess.check_output(['git', '-C', str(candidate), 'rev-parse', 'HEAD'],
                               text=True).strip() != args.target:
        raise ParityError('Candidate SHA mismatch')
    if not Path(args.python).is_file():
        raise ParityError('Python interpreter missing')
    with tempfile.TemporaryDirectory(prefix='tracker751-parity.', dir='/tmp') as private:
        root = Path(private)
        baseline = root / 'base'
        subprocess.run(['git', '-c', f'safe.directory={APP}', '-C', str(APP),
                        'worktree', 'add', '--detach', str(baseline), args.base],
                       check=True, stdout=subprocess.DEVNULL)
        try:
            plugin_dir = candidate / 'scripts'
            if not (plugin_dir / 'tracker_pytest_nodeid751.py').is_file():
                raise ParityError('Pinned parity identity plugin missing')
            run_suite(args.python, baseline, root / 'base-data',
                      root / 'baseline', plugin_dir)
            run_suite(args.python, candidate, root / 'candidate-data',
                      root / 'candidate', plugin_dir)
            result = compare_reports(read_report(root / 'baseline.xml'),
                                     read_report(root / 'candidate.xml'))
            print('RELEASE_751_BACKEND_BASELINE_CASES=' + str(result['baseline_cases']))
            print('RELEASE_751_BACKEND_CANDIDATE_CASES=' + str(result['candidate_cases']))
            print('RELEASE_751_BACKEND_INHERITED_FAILURES=' + str(result['inherited_failures']))
            print('RELEASE_751_BACKEND_BASELINE_PARITY=PASSED')
        finally:
            subprocess.run(['git', '-c', f'safe.directory={APP}', '-C', str(APP),
                            'worktree', 'remove', '--force', str(baseline)],
                           check=True, stdout=subprocess.DEVNULL)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ParityError, subprocess.CalledProcessError, ET.ParseError) as error:
        print('RELEASE_751_BACKEND_BASELINE_PARITY=FAILED', file=sys.stderr)
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(1)
