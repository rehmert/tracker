"""Release 400.1: Labs and COA attachment workspace routing."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from app import config
from app import attachment_files400 as files
from app.attachment_scope396 import require_attachment_scope396
from app.routers import labs, coas


def make_request():
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
def directories(tmp_path, monkeypatch):
    coa = tmp_path / "uploads" / "coa"
    laboratory = tmp_path / "uploads" / "labs"

    coa.mkdir(parents=True)
    laboratory.mkdir(parents=True)

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", coa)
    monkeypatch.setattr(config, "LAB_DIR", laboratory)

    monkeypatch.setattr(
        files.session_auth385,
        "enabled",
        lambda: False,
    )

    return tmp_path, coa, laboratory


def test_both_routers_retain_all_authorization_guards():
    for module in (labs, coas):
        routes = [
            route for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes

        for route in routes:
            guards = {
                item.dependency
                for item in route.dependencies
            }

            assert require_attachment_scope396 in guards
            assert files.require_attachment_workspace400 in guards


def test_existing_directories_are_preserved(directories):
    _, coa, laboratory = directories

    assert files.attachment_directory400("coa") == coa
    assert files.attachment_directory400("labs") == laboratory


def test_identical_filenames_are_separate(directories):
    _, coa, laboratory = directories
    name = "same-name.pdf"

    (coa / name).write_bytes(b"coa-file")
    (laboratory / name).write_bytes(b"lab-file")

    assert files.attachment_file400(
        "coa", name
    ).read_bytes() == b"coa-file"

    assert files.attachment_file400(
        "labs", name
    ).read_bytes() == b"lab-file"


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../secret",
        "folder/file.pdf",
        r"folder\\file.pdf",
        "\x00file",
    ],
)
def test_unsafe_filenames_rejected(directories, name):
    with pytest.raises(HTTPException) as error:
        files.attachment_file400("coa", name)

    assert error.value.status_code == 400


def test_symlinked_attachment_rejected(directories):
    root, coa, _ = directories

    outside = root / "outside.pdf"
    outside.write_bytes(b"private")

    (coa / "linked.pdf").symlink_to(outside)

    with pytest.raises(HTTPException) as error:
        files.attachment_file400("coa", "linked.pdf")

    assert error.value.status_code == 503


def test_symlinked_directory_rejected(directories, monkeypatch):
    root, _, _ = directories

    actual = root / "real"
    actual.mkdir()

    alias = root / "alias"
    alias.symlink_to(actual, target_is_directory=True)

    monkeypatch.setattr(config, "LAB_DIR", alias)

    with pytest.raises(HTTPException) as error:
        files.attachment_directory400("labs")

    assert error.value.status_code == 503


def test_unsupported_category_rejected(directories):
    with pytest.raises(HTTPException) as error:
        files.attachment_directory400("backups")

    assert error.value.status_code == 400


def test_authenticated_storage_mismatch_denied(
    directories, monkeypatch
):
    root, _, _ = directories

    monkeypatch.setattr(
        files.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        config,
        "LAB_DIR",
        root / "other-user" / "labs",
    )

    with pytest.raises(HTTPException) as error:
        files.attachment_directory400("labs")

    assert error.value.status_code == 503


def test_future_user_cannot_access_attachment_router(
    directories, monkeypatch
):
    monkeypatch.setattr(
        files.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        files,
        "authenticated_workspace399",
        lambda _: SimpleNamespace(
            user_id=2,
            mode="reserved-inactive",
        ),
    )

    with pytest.raises(HTTPException) as error:
        files.require_attachment_workspace400(
            make_request()
        )

    assert error.value.status_code == 403


def test_missing_verified_session_denied(
    directories, monkeypatch
):
    monkeypatch.setattr(
        files.session_auth385,
        "enabled",
        lambda: True,
    )

    def deny(_):
        raise HTTPException(
            403, "Verified workspace required"
        )

    monkeypatch.setattr(
        files,
        "authenticated_workspace399",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        files.require_attachment_workspace400(
            make_request()
        )

    assert error.value.status_code == 403


def test_secondary_live_storage_is_still_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
