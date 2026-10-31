#!/usr/bin/env python3
"""Read-only Tracker quality gate. Optional live checks with --url."""

import argparse
import collections
import html.parser
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"


class Scan(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.assets = []
        self.labels = []
        self.controls = []
        self.forms = 0
        self.tables = 0
        self.images_missing_alt = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if "id" in a:
            self.ids.append(a["id"])

        if tag in ("script", "link"):
            value = a.get("src") or a.get("href")
            if value:
                self.assets.append(value)

        if tag == "label" and a.get("for"):
            self.labels.append(a["for"])

        if tag in ("input", "select", "textarea"):
            self.controls.append(
                (
                    a.get("id"),
                    a.get("aria-label"),
                    a.get("type"),
                )
            )

        if tag == "form":
            self.forms += 1

        if tag == "table":
            self.tables += 1

        if tag == "img" and "alt" not in a:
            self.images_missing_alt += 1


def run():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--url",
        help="Optional running Tracker URL"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures"
    )

    parser.add_argument(
        "--json",
        dest="json_path",
        help="Write machine-readable JSON report"
    )

    args = parser.parse_args()

    report = {
        "checks": [],
        "warnings": [],
        "errors": [],
        "stats": {},
    }

    def check(name, ok, detail=""):
        report["checks"].append({
            "name": name,
            "ok": bool(ok),
            "detail": detail,
        })

        print(
            ("PASS" if ok else "FAIL")
            + ": "
            + name
            + (": " + detail if detail else "")
        )

        if not ok:
            report["errors"].append(
                name + (": " + detail if detail else "")
            )

    def warn(message):
        report["warnings"].append(message)
        print("WARN: " + message)

    try:
        from jinja2 import Environment

        environment = Environment(
            extensions=["jinja2.ext.do"]
        )

    except Exception as exc:
        check("Jinja2 available", False, str(exc))
        return 2

    templates = sorted(
        TEMPLATES.rglob("*.html")
    )

    check(
        "Templates found",
        bool(templates),
        str(len(templates))
    )

    asset_refs = collections.defaultdict(list)

    all_forms = 0
    all_tables = 0

    for path in templates:
        relative = path.relative_to(ROOT)

        try:
            source = path.read_text(
                encoding="utf-8"
            )

            environment.parse(source)

        except Exception as exc:
            check(
                f"Jinja syntax {relative}",
                False,
                str(exc)
            )
            continue

        scan = Scan()

        try:
            scan.feed(source)

        except Exception as exc:
            warn(
                f"HTML parser {relative}: {exc}"
            )

        all_forms += scan.forms
        all_tables += scan.tables

        ids = [
            value
            for value in scan.ids
            if "{{" not in value
            and "{%" not in value
        ]

        for identifier, count in collections.Counter(
            ids
        ).items():
            if count > 1:
                warn(
                    f"{relative}: repeated literal ID "
                    f"{identifier!r} ({count} occurrences)"
                )

        if scan.images_missing_alt:
            warn(
                f"{relative}: "
                f"{scan.images_missing_alt} images missing alt"
            )

        for url in scan.assets:
            if (
                url.startswith("/static/")
                and "{{" not in url
                and "{%" not in url
            ):
                name = urllib.parse.urlsplit(
                    url
                ).path.removeprefix("/static/")

                asset_refs[name].append(
                    str(relative)
                )

                check(
                    f"Static asset {name}",
                    (STATIC / name).is_file(),
                    f"referenced by {relative}"
                )

    report["stats"].update({
        "templates": len(templates),
        "forms": all_forms,
        "tables": all_tables,
        "static_assets": len(asset_refs),
    })

    scripts = (
        sorted((STATIC / "js").rglob("*.js"))
        if (STATIC / "js").exists()
        else []
    )

    node = subprocess.run(
        ["bash", "-lc", "command -v node"],
        capture_output=True,
        text=True,
    )

    if node.returncode == 0:
        for path in scripts:
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True,
                text=True,
            )

            check(
                f"JS syntax {path.relative_to(ROOT)}",
                result.returncode == 0,
                result.stderr.strip()[:300],
            )

    else:
        warn(
            "Node.js not installed: "
            "JavaScript checks skipped"
        )

    report["stats"]["javascript_files"] = len(
        scripts
    )

    base = TEMPLATES / "base.html"

    if base.is_file():
        source = base.read_text(
            encoding="utf-8"
        )

        for marker in (
            "tracker-ux-3447-3452.js",
            "tracker-ux-3453-3458.js",
        ):
            count = source.count(marker)

            if count == 0:
                warn(
                    f"Expected UX asset not referenced: "
                    f"{marker}"
                )

            elif count != 1:
                warn(
                    f"Base template references "
                    f"{marker} {count} times"
                )

    if args.url:
        parsed = urllib.parse.urlsplit(
            args.url
        )

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
        ):
            check(
                "Live URL valid",
                False,
                "Use an HTTP or HTTPS base URL"
            )

        else:
            origin = args.url.rstrip("/")

            class LocalRedirect(
                urllib.request.HTTPRedirectHandler
            ):
                def redirect_request(
                    self,
                    req,
                    fp,
                    code,
                    msg,
                    headers,
                    newurl,
                ):
                    destination = urllib.parse.urlsplit(
                        newurl
                    )

                    original = urllib.parse.urlsplit(
                        origin
                    )

                    if destination.netloc != original.netloc:
                        raise urllib.error.HTTPError(
                            newurl,
                            code,
                            "External redirect blocked",
                            headers,
                            fp,
                        )

                    return super().redirect_request(
                        req,
                        fp,
                        code,
                        msg,
                        headers,
                        newurl,
                    )

            opener = urllib.request.build_opener(
                LocalRedirect()
            )

            for route in (
                "/",
                "/vials",
                "/labs",
                "/protocols",
            ):
                try:
                    request = urllib.request.Request(
                        origin + route,
                        method="GET",
                        headers={
                            "User-Agent":
                            "Tracker-Quality-Gate/1.0"
                        },
                    )

                    with opener.open(
                        request,
                        timeout=6,
                    ) as response:
                        status = response.status

                        body = response.read(
                            1024 * 1024
                        )

                        if (
                            status == 200
                            and b"<html" not in body.lower()
                        ):
                            warn(
                                f"{route}: response may "
                                "not be HTML"
                            )

                        check(
                            f"GET {route}",
                            status < 500,
                            f"HTTP {status}",
                        )

                except urllib.error.HTTPError as exc:
                    if exc.code in (401, 403):
                        warn(
                            f"{route}: authentication required "
                            f"(HTTP {exc.code})"
                        )

                    elif exc.code == 404:
                        warn(
                            f"{route}: not found "
                            "(route may differ)"
                        )

                    else:
                        check(
                            f"GET {route}",
                            False,
                            f"HTTP {exc.code}",
                        )

                except Exception as exc:
                    check(
                        f"GET {route}",
                        False,
                        str(exc),
                    )

    print()
    print(
        f"Summary: {len(report['errors'])} failures, "
        f"{len(report['warnings'])} warnings; "
        f"{len(templates)} templates, "
        f"{len(scripts)} JS files"
    )

    # Corrected: json_path is the actual argparse attribute.
    if args.json_path:
        target = pathlib.Path(
            args.json_path
        ).expanduser()

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

        print("Report: " + str(target))

    return (
        1
        if report["errors"]
        or (args.strict and report["warnings"])
        else 0
    )


if __name__ == "__main__":
    sys.exit(run())
