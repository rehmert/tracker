"""Shared rendering for Tracker's read-only tools."""

from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
)
from markupsafe import Markup


TEMPLATE_DIRECTORY = (
    Path(__file__).resolve().parent / "templates"
)

environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIRECTORY)),
    autoescape=select_autoescape(["html"]),
)


def render_tool_page(title, body):
    """Render server-generated tool HTML in Tracker's layout."""
    template = environment.get_template("tool_page.html")

    return template.render(
        title=title,
        body=Markup(body),
        path="",
    )
