from pathlib import Path
from types import SimpleNamespace
from app.pk_template_import import validate


class DB:
    def __init__(self,compound):
        self.compound=compound

    def get(self,model,id):
        if id==self.compound.id:
            return self.compound
        return None

    def scalars(self,query):
        return [self.compound]


def test_portable_compound_resolves_by_name():
    compound=SimpleNamespace(
        id=25,
        name='Example Compound'
    )

    payload=SimpleNamespace(
        compound_id=1,
        compound_name='example compound'
    )

    assert validate(
        DB(compound),payload
    ).id==25


def test_import_file_requires_compound_selection():
    js=Path(
        'app/static/js/tracker-pk-library141.js'
    ).read_text()

    assert 'Switch to compound' in js
    assert 'raw.compound_id' in js


def test_release_guards_present():
    shell=Path(
        'scripts/tracker-release.sh'
    ).read_text()

    assert 'INSTANCE' in shell
    assert 'PROD requires promoted main' in shell
    assert 'restore' in shell.lower()
