"""Canonical anatomical recording locations; never a clinical site guide.

Legacy values are retained verbatim: their precision is not sufficient to
infer a subdivision. Rotation eligibility is explicitly configured.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class Site:
    code: str
    label: str
    region: str
    side: str
    subdivision: str
    views: tuple[str, ...]

def _catalog():
    result = []
    for side in ("left", "right"):
        title = side.title()
        for suffix, label in (("", "lateral / love handle"), ("_mid", "intermediate")):
            result.append(Site(f"abdomen_{side}{suffix}", f"{title} abdomen — {label}",
                               "abdomen", side, label, ("front", side)))
        for part in ("upper", "mid", "lower"):
            label = "middle" if part == "mid" else part
            result.append(Site(f"vastus_lateralis_{side}_{part}", f"{title} lateral thigh — {label}",
                               "thigh", side, label, ("front", side)))
        for part, views in (("anterior", ("front", side)), ("mid", (side,)),
                            ("posterior", ("rear", side))):
            label = "middle" if part == "mid" else part
            result.append(Site(f"deltoid_{side}_{part}", f"{title} deltoid — {label}",
                               "shoulder", side, label, views))
        for height in ("upper", "lower"):
            for width in ("outer", "inner"):
                result.append(Site(f"glute_{side}_{height}_{width}",
                                   f"{title} glute — {height} {width}",
                                   "gluteal", side, f"{height} {width}",
                                   ("rear", side) if width == "outer" else ("rear",)))
    return tuple(result)

SITES = _catalog()
SITE_BY_CODE = {site.code: site for site in SITES}
LEGACY_SITES = ("Abdomen upper left", "Abdomen upper right", "Abdomen lower left",
                "Abdomen lower right", "Quadriceps left", "Quadriceps right",
                "Glute left", "Glute right", "Other / not recorded")
OTHER = "other_unspecified"
INJECTION_SITES = LEGACY_SITES + tuple(SITE_BY_CODE) + (OTHER,)

def site_label(code):
    if code in SITE_BY_CODE:
        return SITE_BY_CODE[code].label
    return "Other / unspecified" if code == OTHER else (code or "Not recorded")

def valid_site(code, *, previous=None):
    """Accept unknown historic labels only when unchanged on correction."""
    return isinstance(code, str) and (code == "" or code in INJECTION_SITES
                                      or (previous is not None and code == previous))

def configured_rotation(configs, *, route, protocol=None, blend=None, compound=None):
    """Most specific explicit route configuration wins; empty disables rotation.

    configs maps (scope, identity, route) to an ordered sequence. No defaults
    are synthesized from the anatomy registry.
    """
    for scope, identity in (("protocol", protocol), ("blend", blend),
                            ("compound", compound), ("global", None)):
        if scope != "global" and identity is None:
            continue
        key = (scope, identity, route)
        if key in configs:
            return tuple(configs[key])
    return ()

def next_rotation_site(sequence, last_site, last_used, excluded, minimum_hours, now):
    """Return next configured recording location or None; never auto-select."""
    if len(set(sequence)) != len(sequence) or any(s not in SITE_BY_CODE for s in sequence):
        raise ValueError("Invalid rotation sequence")
    if not 0 <= minimum_hours <= 8760:
        raise ValueError("Invalid minimum interval")
    start = (sequence.index(last_site) + 1) % len(sequence) if last_site in sequence else 0
    for code in (*sequence[start:], *sequence[:start]):
        if code in excluded:
            continue
        used = last_used.get(code)
        if used is None or now - used >= timedelta(hours=minimum_hours):
            return code
    return None

def site_geometry(code):
    """SVG recording rectangles in a 300×460 schematic, not measured anatomy."""
    site = SITE_BY_CODE.get(code)
    if not site:
        return {}
    side = site.side
    result = {}
    if site.region == "abdomen":
        mid = code.endswith("_mid")
        x = (150 if mid else 174) if side == "left" else (126 if mid else 102)
        result["front"] = (x, 174, 24, 43)
        result[side] = (120 if mid else 144, 174, 24, 43) if side == "left" else (156 if mid else 132, 174, 24, 43)
    elif site.region == "thigh":
        row = {"upper": 0, "middle": 1, "lower": 2}[site.subdivision]
        result["front"] = (178 if side == "left" else 96, 264 + row * 31, 26, 31)
        result[side] = (134, 264 + row * 31, 32, 31)
    elif site.region == "shoulder":
        if site.subdivision == "anterior":
            result["front"] = (205 if side == "left" else 67, 89, 28, 39)
        if site.subdivision == "posterior":
            result["rear"] = (67 if side == "left" else 205, 89, 28, 39)
        column = {"anterior": 0, "middle": 1, "posterior": 2}[site.subdivision]
        if side == "right":
            column = 2 - column
        result[side] = (111 + column * 26, 90, 26, 38)
    elif site.region == "gluteal":
        height, width = site.subdivision.split()
        if side == "left":
            x = 98 if width == "outer" else 124
        else:
            x = 176 if width == "outer" else 150
        y = 220 if height == "upper" else 242
        result["rear"] = (x, y, 26, 22)
        if width == "outer":
            result[side] = (170 if side == "left" else 104, y, 26, 22)
    return result
