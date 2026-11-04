from datetime import datetime
from types import SimpleNamespace
from app.pk_health189 import inspect

class FakeDB:
    def get(self,model,key):
        return SimpleNamespace(id=key)
    def scalars(self,query):
        text=str(query)
        if 'FROM pk_scenarios' in text:
            return [SimpleNamespace(id=1,compound_id=3)]
        if 'FROM pk_planned_doses' in text:
            return [SimpleNamespace(id=2,planned_at=datetime(2026,11,4),amount_mg=1),
                    SimpleNamespace(id=3,planned_at=datetime(2026,11,4),amount_mg=2)]
        raise AssertionError(text)

def test_read_only_duplicate_diagnostic():
    result=inspect(FakeDB())
    assert result['read_only'] is True
    assert result['scenarios_checked']==1
    assert result['findings'][0]['issue']=='duplicate_timestamp'
