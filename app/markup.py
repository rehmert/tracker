"""Small, safe markdown-style renderer for notes pages. Pure Python.

Everything is HTML-escaped first and only this module's own tags are produced,
so the result is safe to mark as trusted. Supported: # headings, - / 1. lists,
> quotes, ``` code blocks, --- rules, **bold**, *italic*, `code`,
[text](https://link), bare http(s) URLs, and [[Page title]] links to other pages.
Only http and https links are ever turned into anchors.
"""
from __future__ import annotations

import re
from html import escape
from typing import Mapping

_STASH = re.compile(r"\x00(\d+)\x00")
_MD_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_WIKI = re.compile(r"\[\[([^\]\n]+)\]\]")
_URL = re.compile(r"https?://(?:(?!&quot;|&lt;|&gt;|&#x27;)\S)+")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![*\w])")
_CODE = re.compile(r"`([^`\n]+)`")


def _anchor(url: str, text: str) -> str:
    return (f'<a href="{url}" target="_blank" rel="noopener noreferrer nofollow">'
            f"{text}</a>")


def _inline(text: str, pages: Mapping[str, int]) -> str:
    """`text` is already HTML-escaped."""
    stash: list[str] = []

    def keep(fragment: str) -> str:
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    text = _CODE.sub(lambda m: keep(f"<code>{m.group(1)}</code>"), text)
    text = _MD_LINK.sub(lambda m: keep(_anchor(m.group(2), m.group(1))), text)

    def wiki(m: re.Match) -> str:
        title = m.group(1).strip()
        pid = pages.get(title.lower().replace("&amp;", "&"))
        if pid is None:
            return keep(f'<span class="wikilink missing" title="No page with this title yet">{title}</span>')
        return keep(f'<a class="wikilink" href="/pages/{pid}">{title}</a>')

    text = _WIKI.sub(wiki, text)

    def bare(m: re.Match) -> str:
        url = m.group(0)
        tail = ""
        while url and url[-1] in ".,;:!?)":
            tail, url = url[-1] + tail, url[:-1]
        return keep(_anchor(url, url)) + tail

    text = _URL.sub(bare, text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    while _STASH.search(text):
        text = _STASH.sub(lambda m: stash[int(m.group(1))], text)
    return text


def render(source: str, pages: Mapping[str, int] | None = None) -> str:
    """`pages` maps lower-cased page titles to ids, for [[wiki links]]."""
    pages = pages or {}
    lines = escape(source or "", quote=True).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    list_kind: str | None = None
    in_code = False
    code: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para:
            out.append("<p>" + _inline(" ".join(para), pages) + "</p>")
            para = []

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
                code, in_code = [], False
            else:
                flush_para(); close_list(); in_code = True
            continue
        if in_code:
            code.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            flush_para(); close_list()
            continue
        if m := re.match(r"^(#{1,3})\s+(.*)$", stripped):
            flush_para(); close_list()
            level = len(m.group(1)) + 1          # page title is the h1
            out.append(f"<h{level}>{_inline(m.group(2), pages)}</h{level}>")
        elif re.match(r"^(-{3,}|\*{3,})$", stripped):
            flush_para(); close_list(); out.append("<hr>")
        elif m := re.match(r"^[-*]\s+(.*)$", stripped):
            flush_para()
            if list_kind != "ul":
                close_list(); out.append("<ul>"); list_kind = "ul"
            out.append(f"<li>{_inline(m.group(1), pages)}</li>")
        elif m := re.match(r"^\d+[.)]\s+(.*)$", stripped):
            flush_para()
            if list_kind != "ol":
                close_list(); out.append("<ol>"); list_kind = "ol"
            out.append(f"<li>{_inline(m.group(1), pages)}</li>")
        elif m := re.match(r"^&gt;\s?(.*)$", stripped):
            flush_para(); close_list()
            out.append(f"<blockquote>{_inline(m.group(1), pages)}</blockquote>")
        else:
            close_list(); para.append(stripped)
    if in_code:
        out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
    flush_para(); close_list()
    return "\n".join(out)


WIKI_RE = re.compile(r"\[\[([^\]\n]+)\]\]")


def wiki_targets(source: str) -> set[str]:
    """Lower-cased titles referenced with [[...]] in raw text."""
    return {m.strip().lower() for m in WIKI_RE.findall(source or "")}
