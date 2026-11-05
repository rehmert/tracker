"""Release 399: request-derived workspace authorization."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from app import config
from app import workspace_boundary399 as boundary
from app.user_storage388 import planned_storage


def request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/labs",
        "raw_path": b"/labs",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


@pytest.fixture
def admin_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "DB_PATH", tmp_path / "tracker.db"
    )
    monkeypatch.setattr(
        config,
        "UPLOAD_DIR",
        tmp_path / "uploads" / "coa",
    )
    monkeypatch.setattr(
        config,
        "LAB_DIR",
        tmp_path / "uploads" / "labs",
    )

    storage = planned_storage(1)

    storage.coa.mkdir(parents=True)
    storage.labs.mkdir(parents=True)
    storage.database.write_bytes(b"test-only-file")

    monkeypatch.setattr(
        boundary,
        "verified_request_scope",
        lambda _: SimpleNamespace(
            user_id=1, storage=storage
        ),
    )

    monkeypatch.setattr(
        boundary,
        "resolve_authenticated_storage",
        lambda _: storage,
    )

    return storage


def test_verified_admin_workspace_resolves(admin_workspace):
    storage = boundary.authenticated_workspace399(
        request()
    )

    assert storage == admin_workspace


def test_valid_attachment_directories(admin_workspace):
    assert boundary.authorized_attachment_dir399(
        request(), "coa"
    ) == admin_workspace.coa

    assert boundary.authorized_attachment_dir399(
        request(), "labs"
    ) == admin_workspace.labs


def test_attachment_name_remains_within_workspace(
    admin_workspace,
):
    candidate = boundary.authorized_attachment_file399(
        request(),
        "coa",
        "stored-file.pdf",
    )

    assert candidate == (
        admin_workspace.coa / "stored-file.pdf"
    )


@pytest.mark.parametrize(
    "name",
    (
        "",
        ".",
        "..",
        "../tracker.db",
        "folder/file.pdf",
        r"folder\file.pdf",
        "\x00file",
    ),
)
def test_unsafe_attachment_names_fail(
    admin_workspace,
    name,
):
    with pytest.raises(HTTPException):
        boundary.authorized_attachment_file399(
            request(), "labs", name
        )


def test_unknown_attachment_kind_rejected(admin_workspace):
    with pytest.raises(HTTPException) as error:
        boundary.authorized_attachment_dir399(
            request(), "backups"
        )

    assert error.value.status_code == 400


def test_secondary_user_scope_cannot_select_storage(
    admin_workspace,
    monkeypatch,
):
    second = planned_storage(2)

    monkeypatch.setattr(
        boundary,
        "verified_request_scope",
        lambda _: SimpleNamespace(
            user_id=2,
            storage=second,
        ),
    )

    monkeypatch.setattr(
        boundary,
        "resolve_authenticated_storage",
        lambda _: second,
    )

    with pytest.raises(HTTPException) as error:
        boundary.authenticated_workspace399(request())

    assert error.value.status_code == 403


def test_mismatched_authenticated_storage_fails(
    admin_workspace,
    monkeypatch,
):
    other = planned_storage(2)

    monkeypatch.setattr(
        boundary,
        "resolve_authenticated_storage",
        lambda _: other,
    )

    with pytest.raises(HTTPException):
        boundary.authenticated_workspace399(request())


def test_mismatched_attachment_directory_fails(
    admin_workspace,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        config,
        "LAB_DIR",
        tmp_path / "wrong-labs",
    )

    with pytest.raises(HTTPException) as error:
        boundary.authenticated_workspace399(request())

    assert error.value.status_code == 503


def test_symlinked_attachment_rejected(
    admin_workspace,
    tmp_path,
):
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")

    link = admin_workspace.coa / "linked.pdf"
    link.symlink_to(outside)

    with pytest.raises(HTTPException) as error:
        boundary.authorized_attachment_file399(
            request(), "coa", "linked.pdf"
        )

    assert error.value.status_code == 503


def test_missing_verified_scope_fails_closed(
    admin_workspace,
    monkeypatch,
):
    def deny(_):
        raise HTTPException(
            403, "Verified session required"
        )

    monkeypatch.setattr(
        boundary,
        "verified_request_scope",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        boundary.authenticated_workspace399(request())

    assert error.value.status_code == 403
