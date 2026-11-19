#!/usr/bin/env python3
"""Read-only Release 704 UI source inventory.

Counts forms and styles without imports of the application, DB or host env.
A count is not a user-visible error or a security finding.
"""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
CSS = ROOT / "app/static/css"
ENHANCED = (
    "dose_edit.html", "page_edit.html", "workout_backfill658.html",
    "preparation_edit.html", "lab_form.html",
)
PREVIOUS = (
    "food_saved_edit669.html", "vitals_edit.html", "compound_edit.html",
)


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = Counter()
        self.links = 0
        self.buttons = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms[a.get("method", "get").lower()] += 1
        if tag == "a":
            self.links += 1
        if tag == "button":
            self.buttons += 1


def report():
    items = []
    for path in sorted(TEMPLATES.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        scan = Inventory()
        scan.feed(source)
        items.append(dict(
            name=path.name,
            post_forms=scan.forms["post"],
            get_forms=scan.forms["get"],
            buttons=scan.buttons,
            links=scan.links,
            edit704=source.count("tracker-edit-actions704\"") == 1,
        ))
    indexed = {item["name"]: item for item in items}
    if any(not indexed.get(name, {}).get("edit704") for name in ENHANCED):
        raise ValueError("Consolidated Release 704 form CSS opt-ins incomplete")
    for name in PREVIOUS:
        if name not in indexed:
            raise ValueError(f"Prior mobile editor missing: {name}")
    return dict(
        template_count=len(items),
        post_form_count=sum(item["post_forms"] for item in items),
        get_form_count=sum(item["get_forms"] for item in items),
        stylesheet_count=len(list(CSS.glob("*.css"))),
        updated_editors=list(ENHANCED),
        existing_editor_coverage=list(PREVIOUS),
        templates_with_post_forms=[
            dict(name=item["name"], count=item["post_forms"])
            for item in items if item["post_forms"]
        ],
        notes=[
            "Static HTML source counts are indicative: Jinja loops and "
            "conditional paths do not equal runtime form counts.",
            "Release 704 does not enable global strict CSRF or upgrade dependencies.",
            "A browser/HTTP security gate and a reproducible wheelhouse are "
            "still required before issues #9 and #10 can be closed.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = report()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        for name in ("template_count", "post_form_count",
                     "get_form_count", "stylesheet_count"):
            print(f"RELEASE_704_{name.upper()}={data[name]}")
        print("RELEASE_704_UPGRADED_EDITORS=" + str(len(data["updated_editors"])))
        print("RELEASE_704_PREVIOUS_EDITORS_PRESERVED=" +
              str(len(data["existing_editor_coverage"])))
        print("RELEASE_704_SECURITY_DEPENDENCY_GATES=NOT_CLOSED")
        print("RELEASE_704_SOURCE_INVENTORY=COLLECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
