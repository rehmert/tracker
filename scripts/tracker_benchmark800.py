"""Isolated synthetic ASGI route benchmark. No live database or external network."""
import argparse
import csv
import html
import json
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROUTES = ("/", "/mobile", "/calendar", "/labs", "/vials", "/planning-hub",
          "/fefo-forecast", "/protocols", "/food", "/workouts/quick")
BASELINE = "fdcdd999891589c3125853c052494330308c8298"
OPTIMIZED = "98509bce1bbc2ce2b4880ddcc844e6a4c9a72633"


def percentile(values, fraction):
    values = sorted(values)
    return values[max(0, __import__("math").ceil(len(values)*fraction)-1)]


def summarize(samples):
    return dict(median_ms=statistics.median(x[0] for x in samples),
                p95_ms=percentile([x[0] for x in samples], .95),
                p99_ms=percentile([x[0] for x in samples], .99),
                median_queries=statistics.median(x[1] for x in samples),
                median_sql_ms=statistics.median(x[2] for x in samples))


def worker(args):
    # Parent supplies a fresh private directory and minimal environment.
    from datetime import date, timedelta
    from fastapi.testclient import TestClient
    from sqlalchemy import event
    from app.main import app
    from app import config
    from app.db import engine, SessionLocal
    from app.models import Compound, Protocol, ProtocolItem, Vial, LabReport, LabResult
    if config.DATA_DIR != Path(os.environ["TRACKER_DATA_DIR"]).resolve():
        raise RuntimeError("Unexpected database path")
    counts = [0, 0.0]
    @event.listens_for(engine, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, executemany):
        context._bench_start = time.perf_counter()
    @event.listens_for(engine, "after_cursor_execute")
    def after(conn, cursor, statement, parameters, context, executemany):
        counts[0] += 1
        counts[1] += (time.perf_counter()-context._bench_start)*1000
    result = {}
    with TestClient(app, follow_redirects=False, auth=("benchmark","synthetic-only")) as client:
        with SessionLocal() as db:
            today = date.today()
            for i in range(12):
                compound = Compound(name=f"Synthetic compound {i}")
                db.add(compound)
                db.flush()
                db.add(Protocol(name=f"Synthetic protocol {i}", is_active=i%3!=0,
                    start_date=today-timedelta(days=7),
                    items=[ProtocolItem(compound_id=compound.id, amount_value=1,
                        amount_unit="mg", freq_count=2, freq_period="week")]))
                for j in range(20):
                    db.add(Vial(compound_id=compound.id, content_value=10,
                        content_unit="mg", expires_on=today+timedelta(days=30+j)))
            for i in range(60):
                db.add(LabReport(drawn_on=today-timedelta(days=i*3), lab_name="Synthetic",
                    results=[LabResult(analyte=f"Synthetic analyte {j}",value=10+i/10,
                        unit="mg/dL") for j in range(20)]))
            db.commit()
        for route in ROUTES:
            samples = []
            for i in range(args.warmup+args.samples):
                counts[:] = [0,0.0]
                start = time.perf_counter()
                response = client.get(route)
                elapsed = (time.perf_counter()-start)*1000
                if response.status_code != 200:
                    raise RuntimeError(f"Route {route}: HTTP {response.status_code}")
                if i >= args.warmup:
                    samples.append((elapsed,*counts))
            result[route] = summarize(samples)
    return dict(routes=result, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def compare(args):
    if os.uname().nodename.split(".")[0] != "tracker-dev":
        raise RuntimeError("Benchmark must run on tracker-dev")
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise RuntimeError("Run with systemd PrivateNetwork=yes")
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {"schema":1,"baseline":args.baseline,"candidate":args.candidate,
              "samples":args.samples,"warmup":args.warmup,"runs":[]}
    for run in range(args.runs):
        pair = {}
        for label, sha in (("baseline",args.baseline),("candidate",args.candidate))[::(-1 if run%2 else 1)]:
            if len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("Exact SHA required")
            with tempfile.TemporaryDirectory(prefix="tracker-bench-") as tmp:
                source = Path(tmp)/"source"
                data = Path(tmp)/"data"
                data.mkdir(mode=0o700)
                subprocess.run(["git","-C",str(root),"worktree","add","--detach",str(source),sha],check=True,stdout=subprocess.DEVNULL)
                try:
                    env = {"PATH":"/usr/bin:/bin","HOME":tmp,"PYTHONPATH":str(source),
                           "TRACKER_DATA_DIR":str(data),"TRACKER_USER":"benchmark",
                           "TRACKER_PASS":"synthetic-only","PYTHONDONTWRITEBYTECODE":"1"}
                    raw = subprocess.check_output([sys.executable,str(Path(__file__).resolve()),
                        "--worker","--samples",str(args.samples),"--warmup",str(args.warmup)],
                        cwd=source,env=env,text=True,timeout=900)
                    pair[label] = json.loads(raw.splitlines()[-1])
                finally:
                    subprocess.run(["git","-C",str(root),"worktree","remove","--force",str(source)],check=True)
        report["runs"].append(pair)
    rows = []
    for route in ROUTES:
        row = {"route":route}
        for metric in ("median_ms","p95_ms","p99_ms","median_queries","median_sql_ms"):
            a,b = [statistics.median(run[label]["routes"][route][metric] for run in report["runs"]) for label in ("baseline","candidate")]
            row.update({metric+"_baseline":a,metric+"_candidate":b,
                        metric+"_change_pct":100*(b-a)/a if a else None})
        row["p95_regression_flag"] = row["p95_ms_candidate"] > row["p95_ms_baseline"]*1.15
        rows.append(row)
    report["comparison"] = rows
    (output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    with (output/"report.csv").open("w") as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    keys=list(rows[0])
    (output/"report.html").write_text("<!doctype html><meta charset=utf-8><title>Tracker benchmark</title><h1>Tracker synthetic ASGI benchmark</h1><table border=1><tr>"+"".join("<th>"+html.escape(k)+"</th>" for k in keys)+"</tr>"+"".join("<tr>"+"".join("<td>"+html.escape(str(round(row[k],3) if isinstance(row[k],float) else row[k]))+"</td>" for k in keys)+"</tr>" for row in rows)+"</table>")
    print(json.dumps(report))


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",action="store_true")
    parser.add_argument("--baseline",default=BASELINE)
    parser.add_argument("--candidate",default=OPTIMIZED)
    parser.add_argument("--samples",type=int,default=100)
    parser.add_argument("--warmup",type=int,default=10)
    parser.add_argument("--runs",type=int,default=3)
    parser.add_argument("--output")
    args=parser.parse_args()
    if not 1<=args.samples<=1000 or not 0<=args.warmup<=100 or not 1<=args.runs<=10:
        parser.error("Invalid sample, warmup or run count")
    if args.worker:
        # Worker is internal only; refuse live paths and shared network.
        data=Path(os.environ.get("TRACKER_DATA_DIR","/")).resolve()
        if not data.parent.name.startswith("tracker-bench-") or data.name!="data" or not data.is_dir() or any(data.iterdir()):
            raise RuntimeError("Fresh benchmark directory required")
        if os.readlink("/proc/self/ns/net")==os.readlink("/proc/1/ns/net"):
            raise RuntimeError("Private network required")
        print(json.dumps(worker(args)))
    elif args.output:
        compare(args)
    else:
        parser.error("--output required")


if __name__=="__main__":
    main()
