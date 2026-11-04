import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from app import config
from app.backup import create_backup, verify_backup
from app.pk_library import save, listing, ExperimentSave
from app.pk_workbench import ExperimentInput


def test_concurrent_saves_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)

    item = SimpleNamespace(
        compound_id=1,
        amount_value=1,
        amount_unit='mg',
        freq_count=1,
        freq_period='week',
        start_week=1,
        end_week=None,
        dose_days='',
        dose_time='08:00',
    )

    protocol = SimpleNamespace(
        name='Example',
        start_date=date(2026, 11, 4),
        end_date=None,
        updated_at=datetime(2026, 11, 4),
        items=[item],
    )

    def one(i):
        return save(
            3,
            protocol,
            ExperimentSave(
                name=f'Experiment {i}',
                settings=ExperimentInput(compound_id=1),
            ),
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(one, range(8)))

    assert len(listing(3)) == 8


def test_backup_includes_saved_experiments(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()

    conn = sqlite3.connect(data / 'tracker.db')
    conn.execute(
        'CREATE TABLE demo(id INTEGER PRIMARY KEY)'
    )
    conn.commit()
    conn.close()

    folder = data / 'uploads' / 'experiments'
    folder.mkdir(parents=True)
    (folder / 'protocol-1.json').write_text('[]')

    backup = create_backup(
        data_dir=data,
        backup_dir=tmp_path / 'backups',
    )
    manifest = verify_backup(backup)

    assert (
        'uploads/experiments/protocol-1.json'
        in manifest['files']
    )


def test_no_stale_preview_cache():
    js = Path(
        'app/static/js/tracker-pk-workbench.js'
    ).read_text()
    assert 'previewCache.get' not in js

    html = Path(
        'app/templates/pk_workspace.html'
    ).read_text()
    assert 'id="pkHomeSearch"' in html
    assert 'Recent recorded administrations' in html

    doses = Path(
        'app/templates/doses.html'
    ).read_text()
    assert 'tracker-dose-mobile104.css?v=bundle104' in doses
