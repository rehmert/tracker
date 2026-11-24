"""Bounded Google Tasks v1 client with OAuth refresh and no secret-bearing errors."""
import os
from urllib.parse import urlencode, quote

import httpx
from . import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_ROOT = "https://tasks.googleapis.com/tasks/v1"
SCOPE = "https://www.googleapis.com/auth/tasks"


class GoogleTasksError769(Exception):
    """A sanitized sync error: no URL, HTTP body or credentials."""


def require_production770():
    """Fail closed for all live OAuth and Google Tasks network entry points."""
    if config.instance_label() != "PROD":
        raise GoogleTasksError769("Live Google Tasks is forbidden outside PROD")


def configured769():
    if config.instance_label() != "PROD":
        return None
    client_id = os.getenv("TRACKER_GOOGLE_TASKS_CLIENT_ID", "").strip()
    secret = os.getenv("TRACKER_GOOGLE_TASKS_CLIENT_SECRET", "").strip()
    redirect = os.getenv("TRACKER_GOOGLE_TASKS_REDIRECT_URI", "").strip()
    valid_redirect = redirect.startswith("https://") or redirect.startswith("http://localhost:")
    if not (client_id and secret and valid_redirect and
            redirect.endswith("/integrations/google-tasks/callback")):
        return None
    return client_id, secret, redirect


def authorization_url769(state):
    require_production770()
    settings = configured769()
    if not settings:
        raise GoogleTasksError769("Google OAuth is not configured")
    client_id, _, redirect = settings
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect,
        "scope": SCOPE, "response_type": "code", "state": state,
        "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "false",
    })


def token_exchange769(data):
    require_production770()
    settings = configured769()
    if not settings:
        raise GoogleTasksError769("Google OAuth is not configured")
    client_id, secret, redirect = settings
    body = dict(data, client_id=client_id, client_secret=secret)
    if "authorization_code" == data.get("grant_type"):
        body["redirect_uri"] = redirect
    try:
        with httpx.Client(timeout=12, trust_env=False) as client:
            response = client.post(TOKEN_URL, data=body)
        if response.status_code != 200:
            raise GoogleTasksError769("Google authorization failed; reconnect from Tracker")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
            raise GoogleTasksError769("Google token response invalid")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise GoogleTasksError769("Google authorization unavailable") from None


class TasksClient769:
    def __init__(self, refresh_token):
        require_production770()
        if not refresh_token:
            raise GoogleTasksError769("Google Tasks is not connected")
        token = token_exchange769({"grant_type": "refresh_token", "refresh_token": refresh_token})
        self._access_token = token["access_token"]
        self._http = httpx.Client(timeout=12, trust_env=False,
                                  headers={"Authorization": "Bearer " + self._access_token})

    def close(self):
        self._http.close()

    def request(self, method, path, *, body=None, params=None):
        require_production770()
        if not path.startswith("/") or path.startswith("//"):
            raise GoogleTasksError769("Invalid Tasks resource")
        try:
            response = self._http.request(method, API_ROOT + path,
                                          json=body, params=params)
            if not 200 <= response.status_code < 300:
                raise GoogleTasksError769(
                    "Google Tasks request rejected; check connection or permissions"
                )
            return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            raise GoogleTasksError769("Google Tasks request unavailable") from None

    @staticmethod
    def _path(value):
        return quote(str(value), safe="")

    def lists(self):
        return self._page("/users/@me/lists", max_results=100)

    def create_list(self, name):
        return self.request("POST", "/users/@me/lists", body={"title": name})

    def tasks(self, list_id):
        return self._page("/lists/" + self._path(list_id) + "/tasks",
                          max_results=100,
                          extra={"showCompleted": "true", "showHidden": "true",
                                 "showDeleted": "true"})

    def _page(self, path, *, max_results=100, extra=None):
        out, token = [], None
        for _ in range(100):
            params = dict(extra or {}, maxResults=max_results)
            if token:
                params["pageToken"] = token
            body = self.request("GET", path, params=params)
            out.extend(body.get("items", []))
            if len(out) > 10000:
                raise GoogleTasksError769("Google task list exceeds sync limit")
            token = body.get("nextPageToken")
            if not token:
                return out
        raise GoogleTasksError769("Google task pagination limit exceeded")

    def create_task(self, list_id, body):
        return self.request("POST", "/lists/" + self._path(list_id) + "/tasks", body=body)

    def patch_task(self, list_id, task_id, body):
        return self.request("PATCH", "/lists/" + self._path(list_id) +
                            "/tasks/" + self._path(task_id), body=body)

    def delete_task(self, list_id, task_id):
        return self.request("DELETE", "/lists/" + self._path(list_id) +
                            "/tasks/" + self._path(task_id))
