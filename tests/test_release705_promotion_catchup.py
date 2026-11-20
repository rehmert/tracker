"""Release 705: narrowly authorized signed DEV-to-PROD UX catch-up.

Pure mocked Git tests: no host/SSH, credentials, pushes, installers, or downloads.
"""
from pathlib import Path
import subprocess

import pytest

from scripts import tracker_promote568 as promote


def simulated_recovery(monkeypatch, *, main=None, base=None, target=None,
                       prod_changed=None, dev_changed=None, remote_ref=None,
                       fail_ancestor=None):
    main = main or promote.RECOVERY_705_MAIN
    base = base or "b" * 40
    target = target or "c" * 40
    allowed = set(promote.RECOVERY_705_ALLOWED)
    if prod_changed is None:
        prod_changed = allowed | {"app/templates/base.html"}
    if dev_changed is None:
        dev_changed = allowed

    commands = []
    def git(*args):
        commands.append(("git", *args))
        if args == ("rev-parse", promote.RECOVERY_705_REF):
            return remote_ref if remote_ref is not None else target
        if args == ("diff", "--name-only", main, target):
            return "\n".join(sorted(dev_changed))
        if args == ("diff", "--name-only", base, target):
            return "\n".join(sorted(prod_changed))
        raise AssertionError(f"Unexpected command {args!r}")

    def run(args):
        commands.append(("run", *args))
        assert args[5:7] == ["merge-base", "--is-ancestor"]
        if fail_ancestor == (args[7], args[8]):
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(promote, "git", git)
    monkeypatch.setattr(promote, "run", run)
    return main, target, base, commands


def test_705_qualified_prod_gap_693_to_704_only_with_exact_source_inventory(monkeypatch):
    main, target, base, events = simulated_recovery(monkeypatch)
    assert promote.recovery_705_prod_lag_allowed(main, target, base)
    ancestry = [(e[8], e[9]) for e in events if e[0] == "run"]
    assert ancestry == [
        (promote.RECOVERY_705_PROD_FLOOR, base),
        (base, promote.RECOVERY_705_MAIN),
        (promote.RECOVERY_705_MAIN, target),
    ]
    assert len(promote.RECOVERY_705_ALLOWED) == 35
    assert "scripts/tracker_promote568.py" in promote.RECOVERY_705_ALLOWED
    assert "scripts/tracker-release.sh" not in promote.RECOVERY_705_ALLOWED
    assert "app/main.py" not in promote.RECOVERY_705_ALLOWED


def test_705_catchup_rejects_unexpected_main_and_moved_ref(monkeypatch):
    main, target, base, _ = simulated_recovery(monkeypatch)
    assert not promote.recovery_705_prod_lag_allowed("a" * 40, target, base)
    simulated_recovery(monkeypatch, remote_ref="f" * 40)
    assert not promote.recovery_705_prod_lag_allowed(main, target, base)


@pytest.mark.parametrize("unsafe", (
    {"scripts/tracker-release.sh"},
    {"app/main.py"},
    {"tests/new-unreviewed-test.py"},
))
def test_705_catchup_rejects_unapproved_new_release_paths(monkeypatch, unsafe):
    main, target, base, _ = simulated_recovery(
        monkeypatch, dev_changed=set(promote.RECOVERY_705_ALLOWED) | unsafe
    )
    assert not promote.recovery_705_prod_lag_allowed(main, target, base)


@pytest.mark.parametrize("path", (
    "deploy/tracker-backup.timer",
    "requirements-dev.txt",
    "requirements.txt",
    "alembic.ini",
    "alembic/versions/upgrade.py",
    "app/db.py",
    "app/models.py",
    "app/workout_models668.py",
))
def test_705_catchup_rejects_unqualified_prod_migration(monkeypatch, path):
    main, target, base, _ = simulated_recovery(
        monkeypatch, prod_changed={"app/templates/base.html", path}
    )
    assert not promote.recovery_705_prod_lag_allowed(main, target, base)


@pytest.mark.parametrize("pair", (
    ("floor", "prod"),
    ("prod", "main"),
    ("main", "target"),
))
def test_705_catchup_requires_all_three_exact_ancestries(monkeypatch, pair):
    main, target, base, _ = simulated_recovery(monkeypatch)
    vals = {
        "floor": promote.RECOVERY_705_PROD_FLOOR,
        "prod": base,
        "main": main,
        "target": target,
    }
    simulated_recovery(monkeypatch, fail_ancestor=(vals[pair[0]], vals[pair[1]]))
    assert not promote.recovery_705_prod_lag_allowed(main, target, base)


def test_705_catchup_signing_and_dev_approval_still_precede_push():
    source = (Path(__file__).resolve().parents[1] / "scripts"
              / "tracker_promote568.py").read_text()
    assert "release == 705 and recovery_705_prod_lag_allowed" in source
    assert "or recovery_705_prod_lag_allowed(main, target, base)" in source
    assert source.index("sign_and_transfer(args.target)") < source.index(
        "promote(args.target, args.prod_base)"
    ) < source.index("deploy(args.release, args.target, args.prod_base)")
    assert "secure_file(log, private=True)" in source
    assert "verified_log(log.read_text" in source
    assert '"/etc/tracker.env"' not in source
    assert "PROD_CATCHUP_705_FROM_MAIN=" in source
