"""Synthetic rolling calculation benchmark; no live data."""
from datetime import date, timedelta
from statistics import median
from timeit import repeat
import subprocess
from app.progress_calc762 import moving762

BASE = "8f12563f1584f1812abe907d2b6f530e63674df8"
namespace = {}
source = subprocess.check_output(["git","show",BASE+":app/progress_calc762.py"],text=True)
exec(compile(source,"baseline-progress-calc","exec"),namespace)
old = namespace["moving762"]
observed = [(date(2020,1,1)+timedelta(days=i),100+i%17/10)
            for i in range(1000) if i%7 != 0]
def run(fn):
    return (fn(observed,7,min_samples=3),fn(observed,28,min_samples=7))
assert run(old) == run(moving762)
before = median(repeat(lambda: run(old), number=1, repeat=3))
after = median(repeat(lambda: run(moving762), number=1, repeat=3))
print(f"RELEASE_806_ROLLING_BENCHMARK=baseline_ms:{before*1000:.3f},candidate_ms:{after*1000:.3f},observations:{len(observed)}",flush=True)
