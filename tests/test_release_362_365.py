import sqlite3
from app.attachment_audit365 import audit_uploads,main


def test_read_only_audit_identifies_missing_and_unreferenced(tmp_path,capsys):
    data=tmp_path/'data';data.mkdir()
    with sqlite3.connect(data/'tracker.db') as db:
        db.execute('CREATE TABLE coas (stored_name TEXT, original_name TEXT)')
        db.execute("INSERT INTO coas VALUES ('present.pdf','uploaded.pdf')")
        db.execute("INSERT INTO coas VALUES ('missing.pdf','missing.pdf')")
    files=data/'uploads'/'coa';files.mkdir(parents=True)
    (files/'present.pdf').write_bytes(b'present')
    (files/'orphan.pdf').write_bytes(b'unreferenced')
    result=audit_uploads(data)
    assert result['missing']==['uploads/coa/missing.pdf']
    assert result['unreferenced_candidates']==['uploads/coa/orphan.pdf']
    assert (files/'orphan.pdf').exists()
    assert main(['--data-dir',str(data)])==2
    assert 'unreferenced_candidates' in capsys.readouterr().out
    assert (files/'orphan.pdf').exists()


def test_audit_reports_symlinks_without_following(tmp_path):
    data=tmp_path/'data';data.mkdir()
    with sqlite3.connect(data/'tracker.db') as db:
        db.execute('CREATE TABLE coas (stored_name TEXT, original_name TEXT)')
    files=data/'uploads'/'coa';files.mkdir(parents=True)
    target=tmp_path/'secret.pdf';target.write_bytes(b'not for scanning')
    (files/'linked.pdf').symlink_to(target)
    report=audit_uploads(data)
    assert report['unsafe_entries']==['uploads/coa/linked.pdf']
    assert report['missing']==[]
    assert target.exists()
