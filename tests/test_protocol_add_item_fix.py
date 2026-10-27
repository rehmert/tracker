"""Regression coverage for adding compounds to a protocol editor."""
from fastapi.testclient import TestClient
from app.main import app


def test_protocol_add_row_and_save():
    with TestClient(app, follow_redirects=True) as client:
        client.post('/compounds', data={'name': 'Protocol Add Row Regression Compound', 'category': 'peptide'})
        created = client.post('/protocols', data={'name': 'Add row regression'})
        editor = client.get(str(created.url))
        assert editor.status_code == 200
        assert 'id="add-protocol-item"' in editor.text
        assert 'novalidate' in editor.text
        row = client.get('/protocols/row')
        assert row.status_code == 200
        assert 'Protocol Add Row Regression Compound' in row.text
        assert 'name="compound_id"' in row.text
        import re
        compound_id = re.search(r'<option value="(\d+)"[^>]*>Protocol Add Row Regression Compound</option>', row.text).group(1)
        saved = client.post(str(created.url).replace('/protocols/', '/protocols/') + '/save', data={
            'name': 'Add row regression', 'compound_id': [compound_id],
            'amount': ['2'], 'unit': ['mg'], 'freq_count': ['1'],
            'freq_period': ['week'], 'horizon_weeks': '12'})
        assert saved.status_code == 200
        assert 'Saved' in saved.text
        assert 'Protocol Add Row Regression Compound' in client.get(str(created.url)).text


def test_new_protocol_shows_editable_compound_fields_without_clicking():
    with TestClient(app, follow_redirects=True) as client:
        client.post('/compounds', data={'name': 'Visible Protocol Compound', 'category': 'peptide'})
        created = client.post('/protocols', data={'name': 'Visible fields test'})
        html = client.get(str(created.url)).text
        assert '<title>Visible fields test · Tracker</title>' in html
        assert 'name="compound_id"' in html
        assert 'name="amount"' in html
        assert 'name="unit"' in html
        assert 'name="freq_count"' in html
        assert 'name="freq_period"' in html
        assert 'hx-get="/protocols/row"' in html
        assert 'hx-swap="beforeend"' in html
        assert 'Visible Protocol Compound' in html
        assert 'data-row-url=' not in html
