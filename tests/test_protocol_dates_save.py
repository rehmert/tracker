"""Protocol dates must persist with either editor submit button."""
import re
from fastapi.testclient import TestClient
from app.main import app


def test_protocol_dates_save_and_add():
    with TestClient(app, follow_redirects=True) as client:
        client.post('/compounds', data={'name': 'Date persistence test compound', 'category': 'peptide'})
        created = client.post('/protocols', data={'name': 'Date persistence test'})
        path = '/protocols/' + str(created.url).split('/protocols/')[-1].split('?')[0]
        html = client.get(path).text
        assert 'name="start_date"' in html and 'name="end_date"' in html
        assert 'action="' + path + '/dates"' not in html
        cid = re.search(r'<option value="(\d+)"[^>]*>Date persistence test compound</option>', html).group(1)
        form = {'name': 'Date persistence test', 'start_date': '2026-10-01', 'end_date': '2026-12-31',
                'compound_id': [cid], 'amount': ['2'], 'unit': ['mg'],
                'freq_count': ['1'], 'freq_period': ['week']}
        saved = client.post(path + '/save', data=form)
        assert saved.status_code == 200
        assert 'value="2026-10-01"' in saved.text
        assert 'value="2026-12-31"' in saved.text
        form['end_date'] = '2027-01-31'
        added = client.post(path + '/add-item', data=form)
        assert added.status_code == 200
        assert 'value="2027-01-31"' in added.text
        invalid = client.post(path + '/save', data={**form, 'end_date': '2026-09-30'})
        assert invalid.status_code == 400
        assert 'value="2027-01-31"' in client.get(path).text
