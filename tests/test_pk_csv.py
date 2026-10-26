"""PK comparison CSV regression tests."""
import csv
import io
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Compound


def test_pk_csv_matches_comparison_and_rejects_bad_ranges():
    with TestClient(app) as client:
      with SessionLocal() as db:
        compound = Compound(name="Tirzepatide", category="peptide")
        db.add(compound)
        db.commit()
        cid = compound.id
      params = {"compound_id": cid, "days_back": 3, "days_forward": 3}
      json_response = client.get('/pk/compare', params=params)
      csv_response = client.get('/pk/compare.csv', params=params)
      assert json_response.status_code == csv_response.status_code == 200
      assert 'attachment;' in csv_response.headers['content-disposition']
      assert csv_response.headers['cache-control'] == 'no-store'
      rows = list(csv.reader(io.StringIO(csv_response.text)))
      result = json_response.json()
      assert rows[0] == ['Timestamp', 'Recorded + decay only']
      assert len(rows) == len(result['at']) + 1
      assert abs((__import__('datetime').datetime.fromisoformat(rows[1][0]) - __import__('datetime').datetime.fromisoformat(result['at'][0])).total_seconds()) < 1
      assert client.get('/pk/compare.csv', params={**params, 'days_back': 500}).status_code == 400
      assert client.get('/pk/compare.csv', params={**params, 'scenario_ids': 'oops'}).status_code == 400
