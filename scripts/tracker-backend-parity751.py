#!/usr/bin/env python3
"""DEV-only full backend parity against pristine Release 750.

Run EVERY backend test on both exact base and candidate; fail if candidate
loses coverage, adds skips/errors/failures, or if either runner fails abnormally.
Legacy failures are retained in private local reports, never declared passed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

APP = Path('/opt/tracker')
FOCUSED_BACKEND_TESTS = (
    'tests/test_core_user_db394.py',
    'tests/test_workouts655.py',
    'tests/test_workouts662.py',
)
# Chromium's computed-style suite operates actual browser subprocesses.
# Running it amid 16 full-backend workers can destabilize the browser;
# execute all five cases separately for both source trees, then merge
# the strict JUnit evidence before comparing every baseline nodeid.
CHROMIUM_676_MODULE = 'tests/test_shortcut_buttons_browser676.py'
CHROMIUM_676_NODEIDS = frozenset(
    CHROMIUM_676_MODULE
    + '::test_676_mobile_links_look_like_daily_shortcut_tiles['
    + str(width) + ']'
    for width in (320, 375, 390, 430, 768)
)
# 662 runs through the live TestClient and assumes no active workout exists.
# The historical test never establishes that precondition. pytest-xdist
# shares a database among files scheduled on the same worker, so previous
# workout tests may leave active state. Run the unmodified 662 module in its
# own disposable DB/process on BOTH versions and keep all results mandatory.
WORKOUTS_662_MODULE = 'tests/test_workouts662.py'
WORKOUTS_662_NODEIDS = frozenset(
    WORKOUTS_662_MODULE + '::' + test
    for test in (
        'test_662_routine_machine_search_and_fast_set_entry_no_new_writes',
        'test_662_untrusted_machine_text_is_escaped_and_existing_routes_unchanged',
        'test_662_template_and_assets_no_mutation_contract',
    )
)
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
        if len(evidence) == 1:
            nodeid = evidence[0]
            if not nodeid or not nodeid.startswith('tests/'):
                raise ParityError('Malformed pytest nodeid')
        elif (not evidence and case.get('classname') == ''
              and case.find('error') is not None
              and case.find('error').get('message') == 'collection failure'):
            # Pytest JUnit creates synthetic testcase entries for collection
            # errors before an Item exists. There can be no user_properties.
            # Keep these as explicit failures, with stable module identities,
            # rather than silently discarding or treating them as ordinary tests.
            import re
            name = case.get('name') or ''
            if not re.fullmatch(r'[A-Za-z0-9_]+(?:[.][A-Za-z0-9_]+)*', name):
                raise ParityError('Malformed collection-error identity')
            nodeid = '__collection__:' + name
        else:
            raise ParityError('Missing or duplicate pytest nodeid property')
        if nodeid in result:
            raise ParityError('Missing or duplicate pytest nodeid')
        result[nodeid] = ('error' if case.find('error') is not None else
                            'failed' if case.find('failure') is not None else
                            'skipped' if case.find('skipped') is not None else
                            'passed')
    return result


def _safe_case_identifier(nodeid: str) -> str | None:
    """Only display source test function + SHA of parameter ID, not test data."""
    import re
    match = re.fullmatch(
        r'(tests/(?:[A-Za-z0-9_]+/)*test_[A-Za-z0-9_]+[.]py)'
        r'::(test_[A-Za-z0-9_]+)(?:\[([^\]\r\n]*)\])?',
        nodeid,
    )
    if not match:
        return None
    path, function, parameter = match.groups()
    if parameter is None:
        return f'{path}::{function}'
    digest = hashlib.sha256(parameter.encode()).hexdigest()[:10]
    return f'{path}::{function}[param_sha256_{digest}]'


# The immutable Release 750 baseline has an import-time assertion in the
# Release 627 module: it expects exactly 161 unsafe routes, while the installed
# application now registers 223. No test items in that module are collected
# on baseline. Release 751 reconciles the current inventory and collects the
# corresponding tests. Only this exact *resolved collection error* can be
# excluded from the "missing test" set; missing actual tests always block.
LEGACY_627_COLLECTION_ERROR = (
    '__collection__:tests.test_release627_csrf_remaining_negative_matrix'
)
LEGACY_627_SOURCE = 'tests/test_release627_csrf_remaining_negative_matrix.py::'
LEGACY_627_REQUIRED_TESTS = (
    'test_635_regimen_unsafe_routes_are_explicit_and_not_source_qualified',
    'test_627_untokened_write_fails_closed',
    'test_627_invalid_signed_header_fails_closed',
    'test_627_session_routes_are_explicitly_excluded_from_global_matrix',
)


def _resolved_627_collection_error(base: dict, candidate: dict) -> bool:
    if base.get(LEGACY_627_COLLECTION_ERROR) != 'error':
        return False
    if LEGACY_627_COLLECTION_ERROR in candidate:
        return False
    if any(nodeid.startswith(LEGACY_627_SOURCE) for nodeid in base):
        # Baseline must have collected zero cases from this module.
        return False
    for test in LEGACY_627_REQUIRED_TESTS:
        prefix = LEGACY_627_SOURCE + test
        matching = [
            value for key, value in candidate.items()
            if key == prefix or key.startswith(prefix + '[')
        ]
        if not matching or any(value != 'passed' for value in matching):
            return False
    return True


def compare_reports(base: dict, candidate: dict) -> dict:
    base_ids, candidate_ids = set(base), set(candidate)
    missing = base_ids - candidate_ids
    if (LEGACY_627_COLLECTION_ERROR in missing
            and _resolved_627_collection_error(base, candidate)):
        missing.remove(LEGACY_627_COLLECTION_ERROR)
        print('RELEASE_751_RESOLVED_LEGACY_627_COLLECTION_ERROR=VERIFIED',
              flush=True)
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
        for collection_id in sorted(missing):
            if collection_id.startswith('__collection__:'):
                import re
                value = collection_id.split(':', 1)[1]
                if re.fullmatch(r'tests(?:[.][A-Za-z0-9_]+)+', value):
                    print('RELEASE_751_UNRESOLVED_COLLECTION_ERROR=' + value,
                          file=sys.stderr)
        for reason, keys in (('MISSING', missing),
                             ('NEW_FAILURE', new_failures),
                             ('NEW_SKIP', new_skips)):
            for nodeid in sorted(keys)[:8]:
                safe_id = _safe_case_identifier(nodeid)
                if safe_id is not None:
                    print('RELEASE_751_PARITY_' + reason + '_CASE=' + safe_id,
                          file=sys.stderr)
        raise ParityError(
            'Backend baseline parity failed: '
            f'missing={len(missing)} new_skips={len(new_skips)} '
            f'new_failures={len(new_failures)}; inspect private JUnit reports'
        )
    inherited = sum(v in ('failed', 'error') for v in candidate.values())
    return {'baseline_cases': len(base), 'candidate_cases': len(candidate),
            'inherited_failures': inherited}


def merge_isolated_chromium676(parallel: dict, isolated: dict) -> dict:
    """Every chromium test is mandatory, exactly once, and passes in isolation."""
    if set(isolated) != CHROMIUM_676_NODEIDS:
        raise ParityError(
            'Chromium 676 JUnit coverage mismatch; expected exactly five cases'
        )
    if any(outcome != 'passed' for outcome in isolated.values()):
        raise ParityError('Chromium 676 isolated run failed or skipped')
    if (set(parallel) & set(isolated)
            or any(key.startswith(CHROMIUM_676_MODULE + '::')
                   for key in parallel)
            or '__collection__:tests.test_shortcut_buttons_browser676' in parallel):
        raise ParityError('Chromium 676 duplicate or leaked parallel test case')
    return parallel | isolated


def merge_isolated_workouts662(parallel: dict, isolated: dict) -> dict:
    """Retain all three original 662 backend tests with isolated worker state."""
    if set(isolated) != WORKOUTS_662_NODEIDS:
        raise ParityError(
            'Workouts 662 JUnit coverage mismatch; expected exactly three cases'
        )
    if any(outcome != 'passed' for outcome in isolated.values()):
        raise ParityError('Workouts 662 isolated run failed or skipped')
    if (set(parallel) & set(isolated)
            or any(key.startswith(WORKOUTS_662_MODULE + '::')
                   for key in parallel)
            or '__collection__:tests.test_workouts662' in parallel):
        raise ParityError('Workouts 662 duplicate or leaked parallel test case')
    return parallel | isolated


def run_suite(python: str, source: Path, data: Path, output: Path,
              plugin_dir: Path, selectors: tuple[str, ...] | None = None,
              *, parallel: bool = True,
              extra_ignores: tuple[str, ...] = ()) -> None:
    data.mkdir(mode=0o700)
    env = dict(os.environ, TRACKER_DATA_DIR=str(data),
               # Source first; shared pinned plugin loaded from candidate.
               PYTHONPATH=os.pathsep.join((str(source), str(plugin_dir))),
               PYTHONDONTWRITEBYTECODE='1')
    argv = [python, '-B', '-m', 'pytest', '-p', 'tracker_pytest_nodeid751',
            '-q', '--tb=short', '--disable-warnings']
    if parallel:
        argv.extend(('-n', '16', '--dist=loadfile'))
    argv.extend(('--durations=20', *(selectors or ('tests',))))
    argv += [f'--ignore={path}' for path in (*IGNORES, *extra_ignores)]
    argv += [f'--junitxml={output}.xml']
    print('RELEASE_751_BACKEND_RUN=' + output.name.upper() + '_STARTED',
          flush=True)
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
    print('RELEASE_751_BACKEND_RUN=' + output.name.upper() + '_FINISHED'
          + '_EXIT_' + str(result.returncode), flush=True)


# Every backend test module gets a fresh pytest process and therefore an
# independent conftest-created SQLite DB on BOTH immutable source trees.
# Sixteen jobs run concurrently; no test case is suppressed or retried.
MODULE_WORKERS_751 = 16
MODULE_TIMEOUT_SECONDS_751 = 600
TREE_TIMEOUT_SECONDS_751 = 1200


def discover_modules751(source: Path, extra_ignores: tuple[str, ...] = ()) -> tuple[str, ...]:
    tests = source / 'tests'
    if not tests.is_dir():
        raise ParityError('Missing source tests tree')
    ignores = (*IGNORES, *extra_ignores)
    modules = {
        file.relative_to(source).as_posix()
        for pattern in ('test_*.py', '*_test.py')
        for file in tests.rglob(pattern)
        if file.is_file() and not file.is_symlink()
    }
    result = tuple(sorted(
        name for name in modules
        if not any(name == ignore or name.startswith(ignore.rstrip('/') + '/')
                   for ignore in ignores)
    ))
    if not result:
        raise ParityError('No backend modules discovered')
    return result


def _module_case_report751(xml: Path, module: str, rc: int,
                           *, allow_legacy_collection: bool) -> dict:
    if not xml.is_file():
        raise ParityError('Missing module JUnit evidence: ' + module)
    if rc == 5:
        # Pytest matched an empty helper file; never accept any lost JUnit
        # cases as an excuse for a no-tests exit.
        if ET.parse(xml).getroot().findall('.//testcase'):
            raise ParityError('Nonempty JUnit on no-tests exit: ' + module)
        return {}
    if rc not in (0, 1, 2):
        raise ParityError('Abnormal module pytest exit: ' + module)
    cases = read_report(xml)
    collection = '__collection__:' + module[:-3].replace('/', '.')
    for key in cases:
        if key != collection and not key.startswith(module + '::'):
            raise ParityError('Unexpected module JUnit identity: ' + module)
    failed = any(value in ('failed', 'error') for value in cases.values())
    if (rc == 0 and failed) or (rc == 1 and not failed):
        raise ParityError('Module JUnit does not match pytest exit: ' + module)
    if rc == 2:
        if not (allow_legacy_collection
                and module == 'tests/test_release627_csrf_remaining_negative_matrix.py'
                and cases == {LEGACY_627_COLLECTION_ERROR: 'error'}):
            raise ParityError('Module collection error blocked: ' + module)
    return cases


def _run_single_module751(python: str, source: Path, plugin_dir: Path,
                          output_root: Path, module: str,
                          *, allow_legacy_collection: bool) -> tuple[str, dict]:
    ident = hashlib.sha256(module.encode('utf-8')).hexdigest()
    run = output_root / ident
    run.mkdir(mode=0o700)
    data = run / 'data'
    data.mkdir(mode=0o700)
    xml = run / 'junit.xml'
    log = run / 'pytest.log'
    env = dict(os.environ, TRACKER_DATA_DIR=str(data),
               PYTHONPATH=os.pathsep.join((str(source), str(plugin_dir))),
               PYTHONDONTWRITEBYTECODE='1')
    argv = [python, '-B', '-m', 'pytest', '-p', 'tracker_pytest_nodeid751',
            '-q', '--tb=short', '--disable-warnings',
            f'--junitxml={xml}', module]
    with log.open('wb') as stream:
        os.chmod(log, 0o600)
        try:
            process = subprocess.run(
                argv, cwd=source, env=env, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT,
                timeout=MODULE_TIMEOUT_SECONDS_751, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ParityError('Backend module timeout: ' + module) from exc
    result = _module_case_report751(
        xml, module, process.returncode,
        allow_legacy_collection=allow_legacy_collection,
    )
    return module, result


def run_isolated_modules751(python: str, source: Path, plugin_dir: Path,
                            output_root: Path,
                            *, allow_legacy_collection: bool = False,
                            extra_ignores: tuple[str, ...] = (),
                            min_cases: int = 4500) -> dict:
    """Exhaustive backend parity with 16 simultaneous fresh-process jobs."""
    output_root.mkdir(mode=0o700)
    modules = discover_modules751(source, extra_ignores)
    print('RELEASE_751_BACKEND_MODULES_DISCOVERED=' + str(len(modules)),
          flush=True)
    results = {}
    pool = ThreadPoolExecutor(max_workers=MODULE_WORKERS_751)
    try:
        futures = {
            pool.submit(_run_single_module751, python, source, plugin_dir,
                        output_root, module,
                        allow_legacy_collection=allow_legacy_collection): module
            for module in modules
        }
        try:
            for future in as_completed(futures, timeout=TREE_TIMEOUT_SECONDS_751):
                module, report = future.result()
                for identity, outcome in report.items():
                    if identity in results:
                        raise ParityError('Duplicate backend test identity')
                    results[identity] = outcome
        except FuturesTimeoutError as exc:
            raise ParityError('Backend module suite exceeded 1200 seconds') from exc
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    if len(results) < min_cases:
        raise ParityError('Backend module coverage unexpectedly low')
    return results


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
            # First compare the previously problematic source modules in
            # disposable processes. A mismatch stops in seconds/minutes,
            # before repeating both 5,000-case backend suites.
            print('RELEASE_751_BACKEND_FOCUSED_PARITY=STARTED', flush=True)
            run_suite(args.python, baseline, root / 'base-focus-data',
                      root / 'baseline-focus', plugin_dir,
                      FOCUSED_BACKEND_TESTS)
            run_suite(args.python, candidate, root / 'candidate-focus-data',
                      root / 'candidate-focus', plugin_dir,
                      FOCUSED_BACKEND_TESTS)
            focused = compare_reports(read_report(root / 'baseline-focus.xml'),
                                      read_report(root / 'candidate-focus.xml'))
            print('RELEASE_751_BACKEND_FOCUSED_PARITY=PASSED', flush=True)
            # All ordinary modules now execute in independent processes.
            # The pre-existing 676 and 662 gates still run separately.
            print('RELEASE_751_BACKEND_MODULE_ISOLATION=STARTED', flush=True)
            print('RELEASE_751_BACKEND_MODULE_PROCESS_WORKERS=16', flush=True)
            base_modules = run_isolated_modules751(
                args.python, baseline, plugin_dir, root / 'baseline',
                allow_legacy_collection=True,
                extra_ignores=(CHROMIUM_676_MODULE, WORKOUTS_662_MODULE,))
            candidate_modules = run_isolated_modules751(
                args.python, candidate, plugin_dir, root / 'candidate',
                extra_ignores=(CHROMIUM_676_MODULE, WORKOUTS_662_MODULE,))
            print('RELEASE_751_BACKEND_MODULE_ISOLATION=PASSED', flush=True)
            print('RELEASE_751_BACKEND_CHROMIUM_676_ISOLATION=STARTED',
                  flush=True)
            run_suite(args.python, baseline, root / 'base-browser676-data',
                      root / 'baseline-browser676', plugin_dir,
                      (CHROMIUM_676_MODULE,), parallel=False)
            run_suite(args.python, candidate, root / 'candidate-browser676-data',
                      root / 'candidate-browser676', plugin_dir,
                      (CHROMIUM_676_MODULE,), parallel=False)
            baseline_report = merge_isolated_chromium676(
                base_modules,
                read_report(root / 'baseline-browser676.xml'))
            candidate_report = merge_isolated_chromium676(
                candidate_modules,
                read_report(root / 'candidate-browser676.xml'))
            print('RELEASE_751_BACKEND_CHROMIUM_676_ISOLATION=PASSED',
                  flush=True)
            print('RELEASE_751_BACKEND_WORKOUTS_662_ISOLATION=STARTED',
                  flush=True)
            run_suite(args.python, baseline, root / 'base-workouts662-data',
                      root / 'baseline-workouts662', plugin_dir,
                      (WORKOUTS_662_MODULE,), parallel=False)
            run_suite(args.python, candidate, root / 'candidate-workouts662-data',
                      root / 'candidate-workouts662', plugin_dir,
                      (WORKOUTS_662_MODULE,), parallel=False)
            baseline_report = merge_isolated_workouts662(
                baseline_report,
                read_report(root / 'baseline-workouts662.xml'))
            candidate_report = merge_isolated_workouts662(
                candidate_report,
                read_report(root / 'candidate-workouts662.xml'))
            print('RELEASE_751_BACKEND_WORKOUTS_662_ISOLATION=PASSED',
                  flush=True)
            result = compare_reports(baseline_report, candidate_report)
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
