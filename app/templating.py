import json
from datetime import date, datetime

from fastapi.templating import Jinja2Templates

from . import calc, config, units as U

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def money(cents) -> str:
    if cents is None:
        return "—"
    sign = "-" if cents < 0 else ""
    return f"{sign}{config.CURRENCY}{abs(cents) / 100:,.2f}"


def money_precise(cents) -> str:
    """For per-unit costs that are fractions of a cent per mcg."""
    if cents is None:
        return "—"
    return f"{config.CURRENCY}{cents / 100:,.4f}"


def amt(base, dim) -> str:
    return U.fmt_amount(base, dim)


def conc(value, dim) -> str:
    return U.fmt_conc(value, dim)


def num(x, digits=4) -> str:
    return "—" if x is None else U._num(float(x), digits)


def dt(x) -> str:
    if isinstance(x, datetime):
        return x.strftime("%Y-%m-%d %H:%M")
    if isinstance(x, date):
        return x.isoformat()
    return "—" if x is None else str(x)


def label_unit(unit: str) -> str:
    return unit


templates.env.filters.update(money=money, money_precise=money_precise, amt=amt, conc=conc,
                             num=num, dt=dt, from_json=json.loads)
templates.env.globals.update(
    DOSE_UNITS=U.DOSE_UNITS, CONTENT_UNITS=U.CONTENT_UNITS,
    PERIOD_LABELS=calc.PERIOD_LABELS, currency=config.CURRENCY)


def render(request, template_name: str, **ctx):
    ctx.setdefault("msg", request.query_params.get("msg"))
    ctx.setdefault("err", request.query_params.get("err"))
    ctx["path"] = request.url.path
    return templates.TemplateResponse(request, template_name, ctx)


def unit_cost(vd) -> str:
    """Landed cost per mg (mass vials) or per IU, for at-a-glance comparison."""
    if vd.content_base <= 0:
        return "—"
    if vd.dim == "iu":
        return f"{money_precise(vd.cost_per_base)} / IU"
    return f"{money(vd.cost_per_base * 1000)} / mg"


templates.env.filters["unit_cost"] = unit_cost


def n1(x) -> str:
    return "—" if x is None else f"{x:,.1f}"


def n0(x) -> str:
    return "—" if x is None else f"{x:,.0f}"


def signed(x) -> str:
    return "—" if x is None else f"{x:+,.1f}"


templates.env.filters.update(n1=n1, n0=n0, signed=signed)


def signed_decimal(x):
    if x is None:
        return "—"
    return ("+" if x > 0 else "") + U._num(float(x))

templates.env.filters["signed_decimal"] = signed_decimal


def num_input(x, digits=4) -> str:
    """Unformatted numeric text for HTML number inputs (commas are invalid)."""
    if x is None:
        return ""
    return U._num(float(x), digits).replace(",", "")

templates.env.filters["num_input"] = num_input
