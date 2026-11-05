import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.db import Base, get_db
from app.models import Compound
from app.routers import exports, record_explorer


def test_http_csv_download(tmp_path):
    engine = create_engine(
        f'sqlite:///{tmp_path / "http-csv.db"}'
    )
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)

    with Session.begin() as db:
        db.add_all([
            Compound(name='=DANGER'),
            Compound(name='Safe')
        ])

    app = FastAPI()
    app.include_router(exports.router)

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override

    with TestClient(app) as client:
        response = client.get(
            '/exports/compounds.csv'
        )

        assert response.status_code == 200
        assert 'text/csv' in response.headers['content-type']
        assert "'=DANGER" in response.text
        assert 'Safe' in response.text
        assert 'no-store' in response.headers['cache-control']

    engine.dispose()


def test_note_diff_budget_returns_413(tmp_path, monkeypatch):
    path = tmp_path / 'notes.db'

    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE pages(
                id INTEGER PRIMARY KEY,
                title TEXT,
                body TEXT
            );
            CREATE TABLE page_revisions(
                id INTEGER PRIMARY KEY,
                page_id INTEGER,
                title TEXT,
                body TEXT,
                created_at TEXT
            );
            INSERT INTO pages VALUES(
                1, 'Big note', 'placeholder'
            );
            INSERT INTO page_revisions VALUES(
                1, 1, 'Big note', 'original', '2026-11-04'
            );
        ''')

        db.execute(
            'UPDATE pages SET body=? WHERE id=1',
            ('x' * 50001,)
        )

    monkeypatch.setattr(
        config,
        'DB_URL',
        f'sqlite:///{path}'
    )

    app = FastAPI()
    app.include_router(record_explorer.router)

    with TestClient(app) as client:
        assert client.get(
            '/record-explorer/notes/1'
        ).status_code == 413
