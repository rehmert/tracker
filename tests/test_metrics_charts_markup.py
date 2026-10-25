from datetime import datetime, timedelta

import pytest

from app import charts, markup, metrics


def test_weight_conversion_roundtrip():
    kg = metrics.weight_to_kg(180, "lb")
    assert kg == pytest.approx(81.6466266)
    assert metrics.weight_from_kg(kg, "lb") == pytest.approx(180)
    assert metrics.weight_to_kg(80, "kg") == 80
    with pytest.raises(ValueError):
        metrics.weight_to_kg(1, "stone")


def test_validation_guards():
    assert metrics.validate(None, None, None, None)
    assert metrics.validate(80, None, None, None) == []
    assert metrics.validate(None, 120, 80, 60) == []
    assert metrics.validate(None, 120, None, None)           # one number only
    assert metrics.validate(None, 80, 120, None)             # swapped
    assert metrics.validate(5, None, None, None)             # typo-sized weight
    assert metrics.validate(None, None, None, 900)


def test_summarize():
    now = datetime(2026, 10, 25, 12)
    pts = [(now - timedelta(days=d), v) for d, v in [(40, 90.0), (20, 82.0), (5, 80.0), (1, 79.0)]]
    s = metrics.summarize(pts, now)
    assert s.n == 4 and s.latest == 79.0
    assert s.avg7 == pytest.approx(79.5)
    assert s.avg30 == pytest.approx((82 + 80 + 79) / 3)
    assert (s.min30, s.max30) == (79.0, 82.0)
    assert s.change30 == pytest.approx(-3.0)
    assert metrics.summarize([], now).latest is None


def test_chart_basic_and_empty():
    now = datetime(2026, 10, 25)
    svg = charts.line_chart([charts.Series("Weight", [(now, 80.0), (now + timedelta(days=1), 79.5)])])
    assert svg.startswith("<svg") and "polyline" in svg and "<circle" in svg
    assert "No readings" in charts.line_chart([])
    one = charts.line_chart([charts.Series("x", [(now, 5.0)])])          # single point, flat range
    assert "circle" in one and "nan" not in one.lower()
    evil = charts.line_chart([charts.Series("<b>x</b>", [(now, 1.0)])])
    assert "<b>" not in evil


def test_markup_blocks_and_inline():
    html = markup.render("# Title\n\nSome **bold** and *it* and `code`.\n\n- a\n- b\n\n1. one\n2. two\n\n> quote")
    for needle in ("<h2>Title</h2>", "<strong>bold</strong>", "<em>it</em>", "<code>code</code>",
                   "<ul>", "<li>a</li>", "<ol>", "<blockquote>quote</blockquote>"):
        assert needle in html


def test_markup_links_and_wikilinks():
    html = markup.render("See [the paper](https://example.org/a?x=1&y=2) and https://example.com/z. Also [[My Page]] and [[Nope]].",
                         {"my page": 7})
    assert 'href="https://example.org/a?x=1&amp;y=2"' in html
    assert 'rel="noopener noreferrer nofollow"' in html
    assert 'href="https://example.com/z"' in html and "</a>. Also" in html   # trailing dot outside link
    assert 'href="/pages/7"' in html and "wikilink missing" in html


def test_markup_is_safe():
    hostile = ('<script>alert(1)</script> [x](javascript:alert(1)) '
               '[y](https://a.com" onmouseover="alert(1)) <img src=x onerror=alert(1)> '
               '[[<b>]] ```\n<script>\n```')
    html = markup.render(hostile)
    assert "<script" not in html and "<img" not in html and "<b>" not in html
    assert 'href="javascript' not in html
    assert 'onmouseover="' not in html
    assert "&lt;script&gt;" in html


def test_wiki_targets():
    assert markup.wiki_targets("a [[One]] b [[ two ]]") == {"one", "two"}
