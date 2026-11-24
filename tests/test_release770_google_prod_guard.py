"""Release 770: assert live Google access is impossible on DEV.

All values are synthetic. No external network or real Tracker data.
"""
import pytest

from app import google_tasks_client769 as client
from app import google_tasks_sync769 as sync
from app.routers import google_tasks769 as router


@pytest.fixture
def synthetic_oauth(monkeypatch):
    monkeypatch.setenv("TRACKER_GOOGLE_TASKS_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("TRACKER_GOOGLE_TASKS_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv(
        "TRACKER_GOOGLE_TASKS_REDIRECT_URI",
        "https://example.test/integrations/google-tasks/callback",
    )
    return monkeypatch


@pytest.mark.parametrize("instance", ["DEV", "", "dev", "TEST", "STAGING"])
def test_770_nonprod_cannot_enable_real_oauth(synthetic_oauth, instance):
    synthetic_oauth.setattr(client.config, "instance_label", lambda: instance)
    assert client.configured769() is None
    with pytest.raises(client.GoogleTasksError769, match="outside PROD"):
        client.authorization_url769("synthetic-state")
    with pytest.raises(client.GoogleTasksError769, match="outside PROD"):
        client.token_exchange769({
            "grant_type": "refresh_token", "refresh_token": "copied-prod-token",
        })
    with pytest.raises(client.GoogleTasksError769, match="outside PROD"):
        client.TasksClient769("copied-prod-token")


def test_770_dev_cannot_use_http_even_with_direct_client_injection(synthetic_oauth):
    synthetic_oauth.setattr(client.config, "instance_label", lambda: "DEV")

    class ForbiddenHTTP:
        def request(self, *args, **kwargs):
            pytest.fail("DEV attempted an outbound Google API request")

    injected = object.__new__(client.TasksClient769)
    injected._http = ForbiddenHTTP()
    with pytest.raises(client.GoogleTasksError769, match="outside PROD"):
        injected.request("POST", "/users/@me/lists", body={"title": "never create"})


def test_770_copied_prod_token_cannot_sync_from_dev(synthetic_oauth, monkeypatch):
    synthetic_oauth.setattr(client.config, "instance_label", lambda: "DEV")

    class CopiedConnection:
        enabled = True
        refresh_token = "copied-prod-token"

    class FakeDB:
        def get(self, *_):
            return CopiedConnection()

    monkeypatch.setattr(sync, "TasksClient769",
                        lambda *_: pytest.fail("DEV created outbound client"))
    assert sync._sync_locked769(FakeDB()) == {
        "status": "disabled", "created": 0, "imported": 0,
        "pending_protocols": 0,
    }


def test_770_dev_connect_sync_and_callback_routes_fail_closed(synthetic_oauth):
    synthetic_oauth.setattr(client.config, "instance_label", lambda: "DEV")
    result = router.begin_connect769()
    assert result.status_code == 303
    assert "DEV" in result.headers["location"]
    result = router.run_sync769()
    assert result.status_code == 303
    assert "DEV" in result.headers["location"]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as denial:
        router.callback769(state="synthetic", code="synthetic")
    assert denial.value.status_code == 403


def test_770_prod_connection_remains_configurable_without_network(synthetic_oauth):
    synthetic_oauth.setattr(client.config, "instance_label", lambda: "PROD")
    assert client.configured769() == (
        "fake-client-id", "fake-secret",
        "https://example.test/integrations/google-tasks/callback",
    )
    url = client.authorization_url769("synthetic-state")
    assert url.startswith(client.AUTH_URL + "?")
    assert "synthetic-state" in url
    assert "fake-secret" not in url
