from pathlib import Path


def test_graph_navigation_and_linked_markers():
    html=Path('app/templates/pk.html').read_text()
    js=Path('app/static/pk.js').read_text()
    graph=Path(
        'app/static/js/tracker-pk-graph137.js'
    ).read_text()

    assert 'id="pkPanLeft"' in html
    assert 'id="pkPanRight"' in html

    assert 'window.trackerPkDrawWindow=draw' in js
    assert 'trackerPkRevealDoseAt' in graph
    assert 'original.rows.slice(begin,end)' in graph
