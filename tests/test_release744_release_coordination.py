"""Release 744: immutable-receipt and CAS tests for two competing Work tasks."""
import json
import pytest
from scripts import tracker_release_coordination744 as c

MAIN="7585b65f003179fe86d0f98958fe0e63071b8e81"
PROD_BASE="c5efed6b40f4324187eff3e83dbed44d9e68f5c4"
NEW="a"*40
NEWER="b"*40


def command(action="prod_deploy", n=743, request_id="r743-deploy7585b65f",
            sha=MAIN, base=PROD_BASE, prev="r743-preflight7585b65f"):
    return dict(schema=1, action=action, release=n, request_id=request_id,
                target=sha, base=base,
                ref=("release/743-security-deps-controller-ux" if n == 743
                     else "release/744-release-coordination"),
                previous_request_id=prev)


def receipt(cmd, status="passed"):
    marker={"qualify":f"RELEASE_{cmd['release']}_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY",
            "dev_install":f"RELEASE_{cmd['release']}_DEV_INSTALL=SUCCESS",
            "prod_preflight":"PREFLIGHT=PASSED",
            "prod_deploy":"PROD_INSTALLED_COMMIT="+cmd["target"]}[cmd["action"]]
    return {**cmd, "status":status, "exit_code":0 if status=="passed" else 42,
            "markers":[marker]+(["DEV_CONTROLLED_RELEASE=SUCCESS"]
                                 if cmd["action"]=="prod_deploy" else [])}


def next_qual():
    return command("qualify",744,"r744-aaaaaaaaaaaa",NEW,MAIN,None)


def run(current=None, last=None, proposed=None, old=None,
        main=MAIN, dev=MAIN, approved=False, branch=None):
    current=current if current is not None else command()
    last=last if last is not None else receipt(command())
    proposed=proposed if proposed is not None else next_qual()
    return c.assess(current,last,proposed,current_receipt=old,
                    main_sha=main,dev_sha=dev,
                    branch_sha=branch if branch is not None else proposed["target"],
                    prod_authorized=approved)


def old_dev():
    return command("dev_install",743,"r743-install7585b65f",MAIN,
                   "8b44bc133d7a0b1582ee11b2acf87809616fab10",
                   "r743-7585b65f0031")


def test_744_successful_743_deploy_with_stale_safety_hold_is_recoverable():
    assert run(old_dev(),old=receipt(old_dev()))=="NEW_RELEASE"


@pytest.mark.parametrize("kind",["missing","notpassed","wrongsha","main_drift",
                                  "dev_drift","same_release","repeat_prod"])
def test_744_stale_hold_only_reconciles_to_next_release(kind):
    past=old_dev(); older=receipt(past); candidate=next_qual(); main=MAIN; dev=MAIN
    if kind=="missing": older=None
    if kind=="notpassed": older["status"]="unknown"
    if kind=="wrongsha": older["target"]=NEW
    if kind=="main_drift": main=PROD_BASE
    if kind=="dev_drift": dev=PROD_BASE
    if kind=="same_release":
        candidate=command("qualify",743,"r743-aaaaaaaaaaaa",NEW,MAIN,None)
    if kind=="repeat_prod":
        candidate=command("prod_deploy",743,"r743-aaaaaaaaaaaa",MAIN,PROD_BASE,
                          "r743-preflight7585b65f")
    with pytest.raises(c.Blocked):
        run(past,old=older,proposed=candidate,main=main,dev=dev,approved=True)


def test_744_pending_queue_cannot_be_overwritten_by_concurrent_work():
    pending=command("qualify",744,"r744-111111111111",NEW,MAIN,None)
    with pytest.raises(c.Blocked):
        run(pending,proposed=command("qualify",744,"r744-222222222222",
                                     NEWER,MAIN,None))


def test_744_qualified_dev_install_requires_same_sha_and_prior_id():
    q=command("qualify",744,"r744-111111111111",NEW,MAIN,None)
    install=command("dev_install",744,"r744-222222222222",NEW,MAIN,q["request_id"])
    assert run(q,receipt(q),install)=="NEXT_STAGE"
    for modified in ({"target":NEWER},{"previous_request_id":"r744-333333333333"},
                     {"base":PROD_BASE}):
        wrong={**install,**modified}
        with pytest.raises(c.Blocked):
            run(q,receipt(q),wrong,branch=wrong["target"])


def test_744_prod_stages_need_authorization_and_installed_base():
    d=command("dev_install",744,"r744-111111111111",NEW,MAIN,
              "r744-222222222222")
    p=command("prod_preflight",744,"r744-333333333333",NEW,MAIN,d["request_id"])
    assert run(d,receipt(d),p,dev=NEW,approved=True)=="NEXT_STAGE"
    for approved,main,base in ((False,MAIN,MAIN),(True,PROD_BASE,MAIN),
                                (True,MAIN,PROD_BASE)):
        with pytest.raises(c.Blocked):
            run(d,receipt(d),{**p,"base":base},dev=NEW,
                main=main,approved=approved)
    deploy=command("prod_deploy",744,"r744-555555555555",NEW,MAIN,p["request_id"])
    assert run(p,receipt(p),deploy,dev=NEW,approved=True)=="NEXT_STAGE"
    with pytest.raises(c.Blocked):
        run(p,receipt(p),deploy,dev=NEW)


def test_744_failed_qa_needs_new_sha_and_new_id():
    q=command("qualify",744,"r744-111111111111",NEW,MAIN,None)
    failed=receipt(q,"failed")
    retry=command("qualify",744,"r744-222222222222",NEWER,MAIN,None)
    assert run(q,failed,retry)=="NEW_SHA_QUALIFICATION"
    for change in ({"target":NEW},{"base":PROD_BASE},
                   {"request_id":q["request_id"]}):
        updated={**retry,**change}
        with pytest.raises(c.Blocked):
            run(q,failed,updated,branch=updated["target"])


@pytest.mark.parametrize("status",["failed","unknown","blocked"])
def test_744_failed_live_stage_never_retried(status):
    d=command("dev_install",744,"r744-111111111111",NEW,MAIN,
              "r744-222222222222")
    with pytest.raises(c.Blocked):
        run(d,receipt(d,status),command("qualify",744,"r744-333333333333",
                                        NEWER,MAIN,None))


def test_744_only_matching_nonexecuted_chain_block_can_retry():
    p=command("prod_preflight",744,"r744-111111111111",NEW,MAIN,
              "r744-222222222222")
    blocked={**receipt(p,"blocked"),"failure_category":"StageChainBlocked"}
    retry={**p,"request_id":"r744-333333333333"}
    assert run(p,blocked,retry,dev=NEW,approved=True)=="NONEXECUTED_CHAIN_RETRY"
    with pytest.raises(c.Blocked):
        run(p,blocked,{**retry,"target":NEWER},dev=NEW,
            branch=NEWER,approved=True)


def test_744_blob_sha_and_snapshot_witnesses(tmp_path,capsys):
    paths={}
    for k,row in (("current",command()),("latest",receipt(command())),
                  ("candidate",next_qual())):
        file=tmp_path/(k+".json");file.write_text(json.dumps(row)+"\n")
        paths[k]=file
    args=[]
    for k in ("current","latest","candidate"):
        args+=["--"+k,str(paths[k])]
    args+=["--main-sha",MAIN,"--dev-sha",MAIN,"--branch-sha",NEW,
           "--expected-current-blob",c.blob_sha(paths["current"].read_bytes()),
           "--expected-latest-id","r743-deploy7585b65f"]
    assert c.main(args)==0
    assert "ALLOW_NEW_RELEASE" in capsys.readouterr().out
    assert c.main(args[:-1]+["r743-mismatch000000"])==2
    assert "snapshot_drift" in capsys.readouterr().err
    wrong=args.copy()
    wrong[wrong.index("--expected-current-blob")+1]=NEWER
    assert c.main(wrong)==2


def test_744_bad_receipt_and_branch_never_authorized():
    for x in ({"markers":[]},{"status":"unknown"},{"target":NEWER}):
        with pytest.raises(c.Blocked):
            run(last={**receipt(command()),**x})
    with pytest.raises(c.Blocked):
        run(proposed={**next_qual(),"ref":"release/745-other"})


def test_744_validator_never_mutates_live_state():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/
            "scripts/tracker_release_coordination744.py").read_text()
    for forbidden in ("subprocess.run(","git push","requests.post(","systemctl",
                      "/etc/tracker.env","os.system("):
        assert forbidden not in source
