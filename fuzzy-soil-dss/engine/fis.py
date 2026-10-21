"""
Mamdani fuzzy inference for soil suitability.

Membership functions and centroid defuzzification come from scikit-fuzzy.
Rule evaluation is written out explicitly so that every firing strength can
be read back and shown to the user as an explanation.

Operators: AND = min, OR = max, NOT = 1 - x, implication = min (clip),
aggregation = max, defuzzification = centroid. The centroid IS the score.
"""
from __future__ import annotations

import numpy as np
import skfuzzy as fuzz

from . import knowledge as K

RESOLUTION = 0.1  # step of the output universe used for aggregation / centroid


# --------------------------------------------------------------------------- #
# Membership function construction
# --------------------------------------------------------------------------- #

def _mf(kind, params, x):
    x = np.asarray(x, dtype=float)
    if kind == "trap":
        return fuzz.trapmf(x, list(params))
    if kind == "tri":
        return fuzz.trimf(x, list(params))
    raise ValueError(kind)


def ph_mfs(crop_key):
    """Crop-specific pH membership functions derived from the S1 and S2 bands.

    The neutral set has full membership across the published S1 range and
    declines to zero across a shoulder that reaches into the S2 band. The
    shoulder is 0.5 pH units, or half the S2 band if that is narrower, so the
    tuples stay monotone whatever the published numbers are.
    """
    c = K.CROPS[crop_key]["ph"]
    a, b = c["s1"]
    low, high = c["s2_low"], c["s2_high"]
    s_lo = min(0.5, (a - low) / 2.0)
    s_hi = min(0.5, (high - b) / 2.0)
    return {
        "strongly_acidic": ("trap", (3.0, 3.0, low - s_lo, low)),
        "moderately_acidic": ("trap", (low - s_lo, low, a - s_lo, a)),
        "neutral": ("trap", (a - s_lo, a, b, b + s_hi)),
        "moderately_alkaline": ("trap", (b, b + s_hi, high, high + s_hi)),
        "strongly_alkaline": ("trap", (high, high + s_hi, 10.0, 10.0)),
    }


def ec_mfs(crop_key):
    """Crop-specific salinity membership functions from the Maas-Hoffman threshold
    `a` (dS/m) and slope `b` (% yield loss per dS/m above `a`).

    Term boundaries follow the Sys et al. (1991) yield bands: S1 above 80 % of
    potential yield, S2 60 to 80 %, S3 40 to 60 %, N below 40 %. So the crossover
    from low to moderate is at 20 % loss, moderate to high at 40 %, high to very
    high at 60 %. Shoulders are half the width of the moderate band.
    """
    c = K.CROPS[crop_key]["ec"]
    a, b = c["a"], c["b"]
    hi = K.FACTORS["ec"]["universe"][1]
    e20, e40, e60 = a + 20.0 / b, a + 40.0 / b, a + 60.0 / b
    d = min(0.5, (e40 - e20) / 2.0)
    c = lambda v: min(v, hi)  # noqa: E731  keep tuples inside the universe
    return {
        "low": ("trap", (0.0, 0.0, c(e20 - d), c(e20 + d))),
        "moderate": ("trap", (c(e20 - d), c(e20 + d), c(e40 - d), c(e40 + d))),
        "high": ("trap", (c(e40 - d), c(e40 + d), c(e60 - d), c(e60 + d))),
        "very_high": ("trap", (c(e60 - d), c(e60 + d), hi, hi)),
    }


def factor_mfs(crop_key, factor):
    """Return {term: (kind, params)} for a numeric factor, crop-specific where needed."""
    if factor == "ph":
        return ph_mfs(crop_key)
    if factor == "ec":
        return ec_mfs(crop_key)
    return K.FACTORS[factor]["mfs"]


def representative_values(crop_key):
    """Midpoint of each term's plateau, used by the linguistic input mode
    ('I only know it is low / moderate / high')."""
    out = {}
    for f in K.FACTOR_ORDER:
        if f == "texture":
            continue
        lo, hi = K.FACTORS[f]["universe"]
        out[f] = {}
        for term, (kind, p) in factor_mfs(crop_key, f).items():
            if kind == "trap":
                mid = (p[1] + p[2]) / 2.0
            else:
                mid = p[1]
            out[f][term] = round(float(np.clip(mid, lo, hi)), 2)
    return out


def mf_curves(crop_key, factor, n=120):
    """Sampled curves for plotting on the front-end."""
    lo, hi = K.FACTORS[factor]["universe"]
    x = np.linspace(lo, hi, n)
    out = {"x": [round(float(v), 3) for v in x], "terms": {}}
    for term, (kind, params) in factor_mfs(crop_key, factor).items():
        out["terms"][term] = [round(float(v), 3) for v in _mf(kind, params, x)]
    return out


# --------------------------------------------------------------------------- #
# Fuzzification
# --------------------------------------------------------------------------- #

def fuzzify(crop_key, inputs):
    """Return {factor: {term: membership}} for the given crisp inputs.

    Memberships are evaluated analytically at the input value (not interpolated
    on a grid), so the universe end points behave exactly like any other value.
    """
    memberships = {}
    for f in K.FACTOR_ORDER:
        if f == "texture":
            cls = inputs["texture"]
            memberships[f] = {t: (1.0 if t == cls else 0.0) for t in K.FACTORS[f]["terms"]}
            continue
        lo, hi = K.FACTORS[f]["universe"]
        v = float(inputs[f])
        if not np.isfinite(v):
            raise ValueError(f"{f} must be a finite number")
        v = float(np.clip(v, lo, hi))
        memberships[f] = {}
        for term, (kind, params) in factor_mfs(crop_key, f).items():
            mu = float(_mf(kind, params, np.array([v]))[0])
            memberships[f][term] = round(mu, 4)
    return memberships


# --------------------------------------------------------------------------- #
# Rule generation
# --------------------------------------------------------------------------- #

def generate_rules(crop_key):
    """Build the rule base for a crop from its rating table (docs/PLAN.md section 2.4).

    Tier 1 (limitation rules), one per factor term rated S3 or N:
        IF f IS t                                 THEN not suitable          (rated N)
        IF f IS t AND NOT (any factor is in an N term) THEN marginally suitable (rated S3)
    The guard on S3 rules keeps a marginal limitation from adding output mass
    once a disqualifying one is present, so adding a problem never raises the score.

    Tier 2 (class rules):
        IF every factor is in an S1 term                              THEN highly suitable
        IF every factor is in an S1 or S2 term AND some factor is in an S2 term THEN moderately suitable
    """
    ratings = K.rating_table(crop_key)
    n_terms = {f: [t for t, r in ratings[f].items() if r == "N"] for f in K.FACTOR_ORDER}
    n_terms = {f: ts for f, ts in n_terms.items() if ts}
    rules = []
    n = 0
    for f in K.FACTOR_ORDER:
        for term, r in ratings[f].items():
            if r in ("S3", "N"):
                n += 1
                rule = {
                    "rule_id": f"{crop_key.upper()[:3]}-L{n:02d}",
                    "crop": crop_key,
                    "tier": 1,
                    "antecedent": {f: [term]},
                    "consequent": "marginally_suitable" if r == "S3" else "not_suitable",
                    "weight": 1.0,
                    "source": _source_for(crop_key, f),
                    "text": f"IF {K.FACTORS[f]['label'].lower()} IS {K.FACTORS[f]['term_labels'][term]}"
                            + (" AND NOT (any factor is in a not-suitable range)" if r == "S3" and n_terms else "")
                            + f" THEN suitability IS {'marginally suitable' if r == 'S3' else 'not suitable'}",
                }
                if r == "S3" and n_terms:
                    rule["not_any"] = n_terms
                rules.append(rule)
    s1_terms = {f: [t for t, r in ratings[f].items() if r == "S1"] for f in K.FACTOR_ORDER}
    s12_terms = {f: [t for t, r in ratings[f].items() if r in ("S1", "S2")] for f in K.FACTOR_ORDER}
    s2_terms = {f: [t for t, r in ratings[f].items() if r == "S2"] for f in K.FACTOR_ORDER}
    s2_terms = {f: ts for f, ts in s2_terms.items() if ts}
    rules.append({
        "rule_id": f"{crop_key.upper()[:3]}-C01",
        "crop": crop_key, "tier": 2,
        "antecedent": s1_terms, "consequent": "highly_suitable", "weight": 1.0,
        "source": "FAO (1976) most-limiting-factor principle",
        "text": "IF every factor is within its highly suitable range THEN suitability IS highly suitable",
    })
    rules.append({
        "rule_id": f"{crop_key.upper()[:3]}-C02",
        "crop": crop_key, "tier": 2,
        "antecedent": s12_terms, "any": s2_terms, "consequent": "moderately_suitable", "weight": 1.0,
        "source": "FAO (1976) most-limiting-factor principle",
        "text": "IF every factor is at least moderately suitable AND some factor is only moderately suitable THEN suitability IS moderately suitable",
    })
    return rules


def _source_for(crop_key, factor):
    if factor == "ph":
        return K.CROPS[crop_key]["ph"]["source"]
    if factor == "ec":
        return K.CROPS[crop_key]["ec"]["source"]
    return K.FACTORS[factor].get("source", "Expert review")


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #

def _or_terms(memberships, f, terms):
    return max((memberships[f].get(t, 0.0) for t in terms), default=0.0)


def _all_factors(memberships, term_lists):
    """AND over factors of (OR over listed terms)."""
    vals = [_or_terms(memberships, f, terms) for f, terms in term_lists.items()]
    return min(vals) if vals else 0.0


def _any_factor(memberships, term_lists):
    """OR over factors of (OR over listed terms)."""
    vals = [_or_terms(memberships, f, terms) for f, terms in term_lists.items()]
    return max(vals) if vals else 0.0


def _rule_strength(rule, memberships):
    s = _all_factors(memberships, rule["antecedent"])
    if rule.get("any"):
        s = min(s, _any_factor(memberships, rule["any"]))
    if rule.get("not_any"):
        s = min(s, 1.0 - _any_factor(memberships, rule["not_any"]))
    if rule.get("not"):  # legacy form: NOT (all factors in listed terms)
        s = min(s, 1.0 - _all_factors(memberships, rule["not"]))
    return s * float(rule.get("weight", 1.0))


def _output_mfs():
    lo, hi = K.OUTPUT["universe"]
    x = np.arange(lo, hi + RESOLUTION / 2, RESOLUTION)
    x = x[x <= hi + 1e-9]
    return x, {t: _mf(kind, p, x) for t, (kind, p) in K.OUTPUT["terms"].items()}


def classify(score):
    for lower, code, label in K.OUTPUT["classes"]:
        if score >= lower:
            return code, label
    return "N", "Not suitable"


_RATING_VALUE = {"S1": 100.0, "S2": 65.0, "S3": 38.0, "N": 10.0}


def factor_scores(crop_key, memberships):
    """Membership-weighted suitability per factor (0..100), for the radar chart."""
    ratings = K.rating_table(crop_key)
    out = {}
    for f in K.FACTOR_ORDER:
        num = sum(mu * _RATING_VALUE[ratings[f][t]] for t, mu in memberships[f].items())
        den = sum(memberships[f].values())
        out[f] = round(num / den, 1) if den > 0 else 0.0
    return out


def evaluate(crop_key, inputs, rules=None):
    """Full Mamdani evaluation. Returns a dict with everything the UI needs."""
    if crop_key not in K.CROPS:
        raise ValueError(f"unknown crop {crop_key}")
    rules = rules or generate_rules(crop_key)
    memberships = fuzzify(crop_key, inputs)

    x, out_mfs = _output_mfs()
    agg = np.zeros_like(x)
    fired = []
    for r in rules:
        s = _rule_strength(r, memberships)
        if s > 1e-6:
            clipped = np.fmin(s, out_mfs[r["consequent"]])
            agg = np.fmax(agg, clipped)
            fired.append({**{k: r[k] for k in ("rule_id", "tier", "consequent", "text", "source")}, "strength": round(float(s), 4)})

    if agg.sum() == 0:
        # Unreachable when every factor's terms partition its universe; kept as a safe default.
        score = 0.0
        code, label = "N", "Not suitable"
    else:
        score = round(float(fuzz.defuzz(x, agg, "centroid")), 1)
        code, label = classify(score)

    ratings = K.rating_table(crop_key)
    sev = {f: i for i, f in enumerate(K.SEVERITY_ORDER)}

    # Limiting factors: fired tier-1 rules, ranked by severity-weighted strength, ties by SEVERITY_ORDER.
    limiting = []
    seen = set()
    tier1 = [fr for fr in fired if fr["tier"] == 1]
    by_id = {r["rule_id"]: r for r in rules}
    def _key(fr):
        rule = by_id[fr["rule_id"]]
        f = next(iter(rule["antecedent"]))
        return (-(fr["strength"] * (2.0 if fr["consequent"] == "not_suitable" else 1.0)), sev[f])
    for fr in sorted(tier1, key=_key):
        rule = by_id[fr["rule_id"]]
        f, (term,) = next(iter(rule["antecedent"].items()))
        if f in seen:
            continue
        seen.add(f)
        limiting.append({
            "factor": f, "label": K.FACTORS[f]["label"], "term": term,
            "term_label": K.FACTORS[f]["term_labels"][term],
            "rating": ratings[f][term], "strength": fr["strength"],
            "advice": K.ADVICE.get(f, {}).get(term, ""),
        })

    # Secondary notes: S2-rated terms with membership >= 0.5 on factors that are not already limiting.
    notes = []
    for f in K.FACTOR_ORDER:
        if f in seen:
            continue
        best = max(((t, mu) for t, mu in memberships[f].items() if ratings[f][t] == "S2"), key=lambda p: p[1], default=None)
        if best and best[1] >= 0.5:
            t, mu = best
            notes.append({
                "factor": f, "label": K.FACTORS[f]["label"], "term": t,
                "term_label": K.FACTORS[f]["term_labels"][t], "rating": "S2", "strength": mu,
                "advice": K.ADVICE.get(f, {}).get(t, ""),
            })
    # Salinity above the crop's Maas-Hoffman threshold is worth naming even while still rated S1.
    ec_in = float(np.clip(float(inputs["ec"]), *K.FACTORS["ec"]["universe"]))
    a, b = K.CROPS[crop_key]["ec"]["a"], K.CROPS[crop_key]["ec"]["b"]
    if ec_in > a and "ec" not in seen and not any(n["factor"] == "ec" for n in notes):
        loss = min(100.0, (ec_in - a) * b)
        notes.append({
            "factor": "ec", "label": K.FACTORS["ec"]["label"], "term": "above_threshold",
            "term_label": f"above the {a:g} dS/m threshold for {K.CROPS[crop_key]['name'].lower()}",
            "rating": "S1", "strength": round(min(1.0, loss / 20.0), 2),
            "advice": f"Salts have passed the point where this crop starts to lose yield. At {ec_in:g} dS/m the expected loss is about {loss:.0f}% (Maas-Hoffman). Leach before planting and watch the irrigation water.",
        })
    notes.sort(key=lambda n: sev[n["factor"]])

    idx = np.linspace(0, len(x) - 1, 101).astype(int)
    return {
        "crop": crop_key,
        "crop_name": K.CROPS[crop_key]["name"],
        "inputs": {f: inputs[f] for f in K.FACTOR_ORDER},
        "score": score,
        "mamdani_centroid": score,
        "class": code,
        "class_label": label,
        "memberships": memberships,
        "factor_scores": factor_scores(crop_key, memberships),
        "fired_rules": sorted(fired, key=lambda r: -r["strength"]),
        "limiting": limiting,
        "notes": notes,
        "output_curve": {"x": [float(x[i]) for i in idx], "y": [round(float(agg[i]), 3) for i in idx]},
        "rule_count": len(rules),
    }
