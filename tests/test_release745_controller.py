"""Release 745: host-side release controller rejects concurrent queue rewinds."""
from pathlib import Path
import importlib.util
import json
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-release-agent745.py"
spec = importlib.util.spec_from_file_location("tracker_agent745", SOURCE)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

A = "a"*40
B = "b"*40
C = "c"*40


def cmd(action, req, release=745, target=B, base=A, previous=None):
    return {"schema":1, "request_id":req, "action":action,"release":release,
            "target":target, "base":base,
            "ref":f"release/{release}-macd-mobile-controller",
            "previous_request_id":previous}


def passed(command):
    return {**command,"status":"passed","exit_code":0}


def transition(old, new, receipt):
    return agent.validate_control_transition(old,new,receipt)


def test_745_qualify_to_dev_install_is_allowed_only_after_immutable_success():
    q=cmd("qualify","r745-aaaaaaaaaaaa")
    d=cmd("dev_install","r745-bbbbbbbbbbbb",previous=q["request_id"])
    transition(q,d,passed(q))
    for receipt in (None,{**passed(q),"status":"failed"},
                    {**passed(q),"target":C}):
        with pytest.raises(agent.GateError):
            transition(q,d,receipt)


def test_745_qualified_prod_progression_has_explicit_matching_stage():
    d=cmd("dev_install","r745-aaaaaaaaaaaa",previous="r745-000000000001")
    pf=cmd("prod_preflight","r745-bbbbbbbbbbbb",base=C,previous=d["request_id"])
    transition(d,pf,passed(d))
    prod=cmd("prod_deploy","r745-cccccccccccc",base=C,previous=pf["request_id"])
    transition(pf,prod,passed(pf))
    for wrong in ({**prod,"base":A},{**prod,"target":C},
                  {**prod,"action":"dev_install"},
                  {**prod,"previous_request_id":d["request_id"]}):
        with pytest.raises(agent.GateError):
            transition(pf,wrong,passed(pf))


def test_745_stale_743_safety_hold_rollback_is_rejected():
    pf=cmd("prod_preflight","r745-aaaaaaaaaaaa",previous="r745-bbbbbbbbbbbb")
    prod=cmd("prod_deploy","r745-cccccccccccc",previous=pf["request_id"])
    transition(pf,prod,passed(pf))
    with pytest.raises(agent.GateError):
        transition(prod,pf,passed(prod))


def test_745_pending_work_cannot_be_overwritten():
    pending=cmd("qualify","r745-aaaaaaaaaaaa")
    other=cmd("qualify","r745-bbbbbbbbbbbb",target=C)
    with pytest.raises(agent.GateError):
        transition(pending,other,None)


def test_745_failed_qualification_restarts_only_at_new_sha():
    q=cmd("qualify","r745-aaaaaaaaaaaa")
    revised=cmd("qualify","r745-bbbbbbbbbbbb",target=C)
    transition(q,revised,{**q,"status":"failed","exit_code":42})
    with pytest.raises(agent.GateError):
        transition(q,{**revised,"target":B},{**q,"status":"failed"})


def test_745_approved_new_release_and_nonexecuted_chain_block():
    prod=cmd("prod_deploy","r745-aaaaaaaaaaaa",previous="r745-bbbbbbbbbbbb")
    new=cmd("qualify","r746-cccccccccccc",release=746,base=B,target=C)
    transition(prod,new,passed(prod))
    blocked=cmd("prod_preflight","r745-bbbbbbbbbbbb",base=C,
                previous="r745-111111111111")
    retry={**blocked,"request_id":"r745-cccccccccccc"}
    transition(blocked,retry,{**blocked,"status":"blocked",
                              "failure_category":"StageChainBlocked"})
    with pytest.raises(agent.GateError):
        transition(blocked,retry,{**blocked,"status":"unknown"})


def test_745_source_installer_only_updates_pinned_agent_binary():
    source=(ROOT/"scripts/tracker-install745.sh").read_text()
    assert "tracker-release-agent745.py" in source
    assert "hash-object" in source
    assert "install -m 0700" in source
    assert "mv -f" in source
    assert "systemctl is-active --quiet tracker" in source
    assert "tracker-release-agent.service" in source
    assert "systemctl show -p Type --value" in source
    assert "systemctl is-active --quiet tracker-release-agent.service" not in source
    assert "git rev-parse" in source


def test_745_controller_history_logic_tracks_every_commit():
    source=SOURCE.read_text()
    assert "git('rev-list', '--reverse'" in source
    assert "validate_control_transition" in source
    assert "control-history745.json" in source
    assert "git('merge-base', '--is-ancestor'" in source
    assert "atomic_json(history_path" in source
    assert "validate_control_ref_history(STATE, control_ref)" in source


def test_745_python_agent_compiles_as_pinned_file():
    compile(SOURCE.read_text(),str(SOURCE),"exec")
