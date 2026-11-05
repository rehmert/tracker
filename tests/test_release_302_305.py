import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.read_only_policy305 import VIEWER_COLUMNS
from app.routers import record_explorer, sqlite_viewer


def test_two_explorers_reject_unknown_tables_and_note_columns(
    monkeypatch,tmp_path
):
    path=tmp_path/'browse.db'

    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE compounds (
                id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                notes TEXT
            );
            INSERT INTO compounds VALUES (
                1,'Safe name','peptide','SENSITIVE_NOTE_302'
            );
            CREATE TABLE vendor_price_attachments (
                id INTEGER, content BLOB
            );
            INSERT INTO vendor_price_attachments
                VALUES (1,X'01020304');
            CREATE TABLE future_api_keys (
                id INTEGER, custom TEXT
            );
            INSERT INTO future_api_keys
                VALUES (1,'SENSITIVE_FUTURE_302');
        ''')

    monkeypatch.setattr(config,'DB_URL',f'sqlite:///{path}')

    app=FastAPI()
    app.include_router(record_explorer.router)
    app.include_router(sqlite_viewer.router)

    with TestClient(app) as client:
        for base in (
            '/record-explorer/database',
            '/sqlite-viewer'
        ):
            index=client.get(base)
            assert index.status_code==200
            assert 'future_api_keys' not in index.text
            assert 'vendor_price_attachments' not in index.text

            known=client.get(base+'?table=compounds')
            assert known.status_code==200
            assert 'Safe name' in known.text
            assert 'SENSITIVE_NOTE_302' not in known.text

            for table in (
                'future_api_keys',
                'vendor_price_attachments'
            ):
                assert client.get(
                    base+'?table='+table
                ).status_code==404

        export=client.get(
            '/sqlite-viewer/export.csv?table=compounds'
        )
        assert export.status_code==200
        assert 'SENSITIVE_NOTE_302' not in export.text

    assert 'notes' not in VIEWER_COLUMNS['compounds']
