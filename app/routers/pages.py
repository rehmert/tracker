import re
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import markup, services
from ..db import get_db
from ..models import SOURCE_KINDS, Compound, Page, Source
from ..templating import render

router = APIRouter()
MAX_BODY = 200_000


def _titles(db: Session) -> dict[str, int]:
    return {p.title.lower(): p.id for p in db.scalars(select(Page))}


def _norm_tags(text: str) -> str:
    tags: list[str] = []
    for raw in re.split(r"[,\n]", text or ""):
        t = raw.strip().lower().lstrip("#")[:40]
        if t and t not in tags:
            tags.append(t)
    return ",".join(tags[:20])


def _snippet(body: str, n: int = 170) -> str:
    flat = re.sub(r"[#>*`\[\]]|\(https?://[^)]*\)", "", body or "")
    flat = " ".join(flat.split())
    return flat if len(flat) <= n else flat[:n].rstrip() + "…"


def _matches(p: Page, q: str) -> bool:
    hay = [p.title, p.body, p.tags] + [f"{s.title} {s.author} {s.url or ''} {s.publication}"
                                       for s in p.sources]
    return any(q in h.lower() for h in hay)


@router.get("/pages")
def pages_list(request: Request, q: str = "", tag: str = "", compound_id: int | None = None,
               db: Session = Depends(get_db)):
    all_pages = list(db.scalars(select(Page).order_by(Page.updated_at.desc(), Page.id.desc())))
    pages = all_pages
    if q.strip():
        needle = q.strip().lower()
        pages = [p for p in pages if _matches(p, needle)]
    if tag:
        pages = [p for p in pages if tag in p.tag_list]
    if compound_id:
        pages = [p for p in pages if any(c.id == compound_id for c in p.compounds)]
    return render(request, "pages.html", pages=pages, q=q, tag=tag, compound_id=compound_id,
                  all_tags=sorted({t for p in all_pages for t in p.tag_list}),
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  snippet=_snippet, total=len(all_pages))


@router.get("/pages/new")
def new_page(request: Request, title: str = "", db: Session = Depends(get_db)):
    return render(request, "page_edit.html", p=None, title=title[:200],
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  selected=set())


@router.post("/pages/preview")
def preview(body: str = Form(""), db: Session = Depends(get_db)):
    return HTMLResponse(markup.render(body[:MAX_BODY], _titles(db)))


def _validate(db: Session, title: str, body: str, exclude_id: int | None) -> str | None:
    title = title.strip()
    if not title:
        return "Give the page a title."
    if len(body) > MAX_BODY:
        return "That page is too long (200,000 character limit)."
    for p in db.scalars(select(Page)):
        if p.title.lower() == title.lower() and p.id != exclude_id:
            return f"A page called '{p.title}' already exists."
    return None


@router.post("/pages")
def create_page(title: str = Form(""), body: str = Form(""), tags: str = Form(""),
                compound_ids: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    err = _validate(db, title, body, None)
    if err:
        return services.flash_redirect(f"/pages/new?title={quote(title.strip()[:200])}", err=err)
    p = Page(title=title.strip(), body=body, tags=_norm_tags(tags))
    if compound_ids:
        p.compounds = list(db.scalars(select(Compound).where(Compound.id.in_(compound_ids))))
    db.add(p)
    db.commit()
    return services.flash_redirect(f"/pages/{p.id}", msg="Page created. Add sources below.")


def _get(db: Session, pid: int) -> Page:
    p = db.get(Page, pid)
    if p is None:
        raise HTTPException(404, "Page not found")
    return p


@router.get("/pages/{pid}")
def view_page(pid: int, request: Request, db: Session = Depends(get_db)):
    p = _get(db, pid)
    me = p.title.lower()
    backlinks = [o for o in db.scalars(select(Page)) if o.id != pid
                 and me in markup.wiki_targets(o.body)]
    return render(request, "page_view.html", p=p, html=markup.render(p.body, _titles(db)),
                  backlinks=backlinks, kinds=SOURCE_KINDS, today=date.today().isoformat())


@router.get("/pages/{pid}/edit")
def edit_page(pid: int, request: Request, db: Session = Depends(get_db)):
    p = _get(db, pid)
    return render(request, "page_edit.html", p=p, title=p.title,
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  selected={c.id for c in p.compounds})


@router.post("/pages/{pid}")
def update_page(pid: int, title: str = Form(""), body: str = Form(""), tags: str = Form(""),
                compound_ids: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    p = _get(db, pid)
    err = _validate(db, title, body, pid)
    if err:
        return services.flash_redirect(f"/pages/{pid}/edit", err=err)
    p.title, p.body, p.tags = title.strip(), body, _norm_tags(tags)
    p.compounds = list(db.scalars(select(Compound).where(Compound.id.in_(compound_ids)))) \
        if compound_ids else []
    db.commit()
    return services.flash_redirect(f"/pages/{pid}", msg="Page saved.")


@router.post("/pages/{pid}/delete")
def delete_page(pid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, pid))
    db.commit()
    return services.flash_redirect("/pages", msg="Page deleted.")


@router.post("/pages/{pid}/sources")
def add_source(pid: int, kind: str = Form("web"), title: str = Form(""), url: str = Form(""),
               author: str = Form(""), publication: str = Form(""), location: str = Form(""),
               accessed_on: str = Form(""), note: str = Form(""), db: Session = Depends(get_db)):
    _get(db, pid)
    back = f"/pages/{pid}"
    url = url.strip()
    try:
        if not (title.strip() or url):
            raise ValueError("Give the source a title or a link.")
        if url and (not re.match(r"^https?://\S+$", url, re.I) or len(url) > 2000):
            raise ValueError("Links must start with http:// or https:// and contain no spaces.")
        when = services.parse_date(accessed_on)
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    db.add(Source(page_id=pid, kind=kind if kind in SOURCE_KINDS else "other",
                  title=title.strip()[:300], url=url or None, author=author.strip()[:200],
                  publication=publication.strip()[:200], location=location.strip()[:120],
                  accessed_on=when, note=note.strip()))
    db.commit()
    return services.flash_redirect(back, msg="Source added.")


@router.post("/sources/{sid}/delete")
def delete_source(sid: int, db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    if s is None:
        raise HTTPException(404, "Source not found")
    pid = s.page_id
    db.delete(s)
    db.commit()
    return services.flash_redirect(f"/pages/{pid}", msg="Source removed.")
