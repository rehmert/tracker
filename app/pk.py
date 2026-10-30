"""Exploratory one-compartment exposure model. NOT a serum assay or dose advice."""
from datetime import datetime, timedelta
from math import exp, log, isfinite
import re

LN2 = log(2)
# Defaults are approximate, formulation-dependent, and editable by the user.
PROFILES = {
    "tirzepatide": (120.0, 12.0),
    "semaglutide": (168.0, 24.0),
    "liraglutide": (13.0, 3.0),  # human SC elimination; absorption approximate
    "exenatide": (2.4, 0.65),  # immediate-release SC; absorption approximate
    "retatrutide": (144.0, 24.0),
    "testosterone cypionate": (192.0, 24.0),
    "testosterone enanthate": (120.0, 24.0),
    "testosterone": (192.0, 24.0),
    "tesamorelin": (11.0 / 60.0, 0.05),  # WR elimination estimate; absorption illustrative
    "ipamorelin": (2.0, 0.5),  # IV elimination reference; SC absorption illustrative
    "bpc-157": (1.0, 1.0),  # UI placeholders ONLY: no human PK defaults

}

def profile(name: str):
    label = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    if any(x in label for x in ("propionate", "undecanoate", "gel", "cream", "oral", "pellet", "extended release", "bydureon")):
        return None
    if "testosterone" in label or label == "trt":
        if "enanthate" in label:
            return PROFILES["testosterone enanthate"]
        return PROFILES["testosterone cypionate"]
    if "tesamorelin" in label or "tesamoralin" in label or label == "tesa":
        return PROFILES["tesamorelin"]
    if "ipamorelin" in label or "ipalmorelin" in label or label == "ipa":
        return PROFILES["ipamorelin"]
    if re.search(r"\bbpc\s*157\b", label):
        return PROFILES["bpc-157"]
    for key in ("tirzepatide", "semaglutide", "liraglutide", "exenatide", "retatrutide"):
        if re.search(r"\b" + key + r"\b", label):
            return PROFILES[key]
    return None

def exposure_at(at: datetime, doses: list[tuple[datetime, float]], half_life_hours: float,
                absorption_half_life_hours: float) -> float:
    """Apparent mg-equivalent exposure with first-order absorption and elimination.

    Uses normalized absorbed fraction; excludes bioavailability and distribution volume.
    For k_a ~= k_e uses the analytic limit to avoid division by zero.
    """
    if not (isfinite(half_life_hours) and isfinite(absorption_half_life_hours)) or min(half_life_hours, absorption_half_life_hours) <= 0:
        raise ValueError("Half-lives must be positive finite numbers")
    ke, ka = LN2 / half_life_hours, LN2 / absorption_half_life_hours
    total = 0.0
    for when, amount in doses:
        if not isfinite(amount) or amount <= 0:
            raise ValueError("Dose must be positive and finite")
        h = (at - when).total_seconds() / 3600
        if h < 0:
            continue
        if abs(ka - ke) < 1e-10:
            fraction = ka * h * exp(-ke * h)
        else:
            fraction = ka / (ka - ke) * (exp(-ke * h) - exp(-ka * h))
        total += amount * fraction
    return max(0.0, total)

def series(start: datetime, end: datetime, actual: list[tuple[datetime, float]],
           planned: list[tuple[datetime, float]], half_life_hours: float,
           absorption_half_life_hours: float, step_hours: float = 12):
    if end <= start or (end-start).days > 730:
        raise ValueError("Choose a date range of at most 730 days")
    if not (isfinite(step_hours) and 0.01 <= step_hours <= 168):
        raise ValueError("Invalid graph resolution")
    rows = []
    t = start
    while t <= end:
        baseline = exposure_at(t, actual, half_life_hours, absorption_half_life_hours)
        rows.append({"at": t.isoformat(), "actual": round(baseline, 5),
                     "planned": round(baseline + exposure_at(t, planned, half_life_hours, absorption_half_life_hours), 5)})
        t += timedelta(hours=step_hours)
    return rows


def model_info(name: str) -> dict:
    """Evidence label and limitations, not a clinical PK assertion."""
    label = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    if re.search(r"\bbpc\s*157\b", label):
        return {"level": "illustrative", "needs_assumptions": True,
                "description": "No validated human subcutaneous PK. Enter both hypothetical half-lives; output is illustrative only."}
    if "ipamorelin" in label or "ipalmorelin" in label or label == "ipa":
        return {"level": "experimental", "needs_assumptions": False,
                "description": "Elimination estimate from human IV research (~2 h); subcutaneous absorption is assumed, not validated."}
    if "tesamorelin" in label or "tesamoralin" in label or label == "tesa":
        return {"level": "formulation-specific", "needs_assumptions": False,
                "description": "11-minute elimination reference for EGRIFTA WR; other formulations differ. Absorption half-life is illustrative."}
    if "liraglutide" in label:
        return {"level": "human elimination", "needs_assumptions": False,
                "description": "Human SC elimination half-life approximately 13 h (FDA label); absorption shape is an approximation. Injection formulation only."}
    if "exenatide" in label:
        return {"level": "human elimination", "needs_assumptions": False,
                "description": "Immediate-release SC exenatide elimination half-life approximately 2.4 h (FDA label). NOT extended-release exenatide; absorption shape approximate."}
    if "semaglutide" in label:
        return {"level": "human elimination", "needs_assumptions": False,
                "description": "Injectable semaglutide elimination half-life approximately 1 week (FDA label); absorption is approximate, not oral semaglutide."}
    return {"level": "approximate", "needs_assumptions": False,
            "description": "Exploratory one-compartment exposure model; not measured serum concentration."}
