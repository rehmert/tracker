"""Release 806: exact rolling windows, plateau coverage and safe progress context."""
from datetime import date, datetime, time, timedelta
from statistics import mean
from urllib.parse import urlsplit, parse_qs
from pathlib import Path
import pytest
from starlette.requests import Request
from app.progress_calc762 import moving762, weight_report762
from app.routers.progress762 import _progress_filters806, _progress_redirect806

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("days,minimum", [(7,3),(28,7),(1,1),(28,99)])
def test_rolling_matches_original_sparse_unsorted_windows(days, minimum):
    start = date(2023, 1, 1)
    observed = [(start + timedelta(days=i), 100.0 + i/7) for i in range(91) if i % 5]
    observed = observed[::2] + observed[1::2]
    expected = []
    for day, _ in observed:
        values = [v for d,v in observed if day-timedelta(days=days-1) <= d <= day]
        if len(values) >= minimum:
            expected.append((datetime.combine(day,time(12)), mean(values), len(values)))
    assert moving762(observed,days,min_samples=minimum) == expected
    assert moving762([],days,min_samples=minimum) == []

def test_plateau_requires_all_four_weeks_to_be_stable():
    today = date(2026,1,28)
    def rows(weekly):
        return sorted((today-timedelta(days=7*w+d), value)
                      for w,value in enumerate(weekly) for d in (0,2,4))
    stable = weight_report762(rows([100,100.1,99.9,100]),today)
    assert stable["plateau"] is True
    assert stable["plateau_week_counts"] == (3,3,3,3)
    assert weight_report762(rows([100,104,102,100]),today)["plateau"] is False
    assert weight_report762(rows([100,100,100,100])[:-1],today)["plateau"] is None

def test_context_redirect_keeps_filters_and_flash_before_anchor():
    req = Request({"type":"http","method":"POST","path":"/progress/measure/save",
                   "query_string":b"days=30&markers=1&machine=12&reps=8&analyte=apo%26b&next=https://example.com"})
    response = _progress_redirect806(req,"measure",err="Invalid value",edit_id=7)
    parts = urlsplit(response.headers["location"])
    assert response.status_code == 303 and parts.path == "/progress" and parts.fragment == "measure"
    assert parse_qs(parts.query) == {"days":["30"],"markers":["1"],"machine":["12"],"reps":["8"],
        "analyte":["apo&b"],"edit_kind":["measure"],"edit_id":["7"],"err":["Invalid value"]}
    assert _progress_filters806({"days":"-1","machine":"0","reps":"201","markers":"2",
                                  "next":"//example.com","analyte":"a"*257}) == {}
    assert _progress_redirect806(req,"marker",msg="Saved").headers["location"].endswith("#marker")

def test_progress_templates_preserve_context():
    template = (ROOT/"app/templates/progress762.html").read_text()
    import re
    actions = re.findall(r'<form method="post" action="([^"]+)"', template)
    assert len(actions) == 10
    assert "/progress/milestones807?{{ progress_query }}" in actions
    assert all("?{{ progress_query }}" in action for action in actions)
    assert template.count("{{ progress_query }}&amp;edit_kind=") == 4
    assert 'action="/progress#progress-strength"' in template
    assert 'action="/progress#progress-labs"' in template
