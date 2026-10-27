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
