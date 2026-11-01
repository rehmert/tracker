"""Shared rendering for Tracker's read-only tool pages.

Use the application's configured Jinja environment, including its filters
and globals (such as the per-instance DEV/PROD badge). A second Jinja
environment silently drifts when the shared base template changes.
"""

from markupsafe import Markup

from .templating import templates


def render_tool_page(title, body):
    """Render trusted, server-generated tool HTML in Tracker's layout."""
    template = templates.env.get_template("tool_page.html")

    return template.render(
        title=title,
        body=Markup(body),
        path="",
    )
