"""
Evaluation script for Chapter Four. Produces every number reported in the chapter.

Run from the project folder:
    python tests/evaluate_system.py
Writes docs/evaluation/results.json and prints a summary.

Sections
  1. rule base composition per crop
  2. worked examples (memberships, fired rules, centroid)
  3. real-life scenarios (15 plots, expected class written before running)
  4. agro-ecological zone presets x crops matrix
  5. comparative validation: fuzzy engine vs a crisp FAO/Sys "most limiting factor" classifier
     on 1,200 synthetic plots drawn from ranges typical of Nigerian vegetable soils
  6. boundary behaviour: score sweeps for pH and salinity, fuzzy vs crisp
  7. engine speed
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import evaluate, knowledge as K  # noqa: E402
from engine.fis import fuzzify, generate_rules, classify  # noqa: E402

OUT = os.path.join(ROOT, "docs", "evaluation")
os.makedirs(OUT, exist_ok=True)
R = {}

CLASS_ORDER = ["S1", "S2", "S3", "N"]
WORST = {c: i for i, c in enumerate(CLASS_ORDER)}


# ------------------------------------------------------------------ 1. rule base
R["rules"] = {}
for c in K.CROP_ORDER:
    rules = generate_rules(c)
    R["rules"][c] = {
        "total": len(rules),
        "not_suitable": sum(1 for r in rules if r["tier"] == 1 and r["consequent"] == "not_suitable"),
        "marginal": sum(1 for r in rules if r["tier"] == 1 and r["consequent"] == "marginally_suitable"),
        "class_rules": sum(1 for r in rules if r["tier"] == 2),
    }
R["rules_total"] = sum(v["total"] for v in R["rules"].values())
R["mf_count"] = {
    "shared": sum(len(K.FACTORS[f]["terms"]) for f in ("nitrogen", "phosphorus", "potassium", "organic_carbon", "moisture")),
    "crop_specific_per_crop": len(K.FACTORS["ph"]["terms"]) + len(K.FACTORS["ec"]["terms"]),
}
R["mf_count"]["total"] = R["mf_count"]["shared"] + len(K.CROP_ORDER) * R["mf_count"]["crop_specific_per_crop"]


# ------------------------------------------------------------------ 2. worked examples
def brief(res):
    return {
        "score": res["score"], "class": res["class"],
        "fired": [(f["rule_id"], f["strength"], f["consequent"]) for f in res["fired_rules"]],
        "limiting": [(l["factor"], l["term"], l["rating"], l["strength"]) for l in res["limiting"]],
        "notes": [(n["factor"], n["term"]) for n in res["notes"]],
        "memberships": res["memberships"],
        "factor_scores": res["factor_scores"],
    }


EX = {
    "tomato_worked": ("tomato", dict(ph=5.6, nitrogen=1.2, phosphorus=10, potassium=0.2, organic_carbon=0.9, ec=1.0, moisture=65, texture="loam")),
    "tomato_r1": ("tomato", dict(ph=6.5, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.5, moisture=65, texture="loam")),
    "tomato_ph58": ("tomato", dict(ph=5.8, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.5, moisture=65, texture="loam")),
    "tomato_worked_ph58": ("tomato", dict(ph=5.8, nitrogen=1.2, phosphorus=10, potassium=0.2, organic_carbon=0.9, ec=1.0, moisture=65, texture="loam")),
    "onion_saline": ("onion", dict(ph=6.5, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=3.6, moisture=65, texture="loam")),
}
R["examples"] = {k: brief(evaluate(c, i)) for k, (c, i) in EX.items()}


# ------------------------------------------------------------------ 3. scenarios
SCEN = [
    ("Kadawa irrigation scheme, Kano", "tomato", dict(ph=6.6, nitrogen=0.7, phosphorus=9, potassium=0.25, organic_carbon=0.45, ec=1.4, moisture=55, texture="sandy_loam"), "S3"),
    ("Vom, Jos Plateau (manured highland loam)", "cabbage", dict(ph=5.9, nitrogen=2.2, phosphorus=22, potassium=0.4, organic_carbon=1.9, ec=0.3, moisture=70, texture="loam"), "S1/S2"),
    ("Ikorodu, Lagos (3 years poultry manure, borehole)", "amaranth", dict(ph=6.2, nitrogen=2.5, phosphorus=35, potassium=0.6, organic_carbon=2.4, ec=3.6, moisture=70, texture="sandy_loam"), "S1/S2"),
    ("Badagry, Lagos (fresh acid sand)", "pepper", dict(ph=4.6, nitrogen=0.6, phosphorus=4, potassium=0.08, organic_carbon=0.5, ec=0.3, moisture=60, texture="sandy"), "S3"),
    ("Yenagoa, Bayelsa (waterlogged backswamp clay)", "onion", dict(ph=5.0, nitrogen=1.9, phosphorus=9, potassium=0.3, organic_carbon=2.6, ec=2.8, moisture=105, texture="clay"), "N"),
    ("Yenagoa, Bayelsa (same plot)", "okra", dict(ph=5.0, nitrogen=1.9, phosphorus=9, potassium=0.3, organic_carbon=2.6, ec=2.8, moisture=105, texture="clay"), "S3"),
    ("Sokoto-Rima fadama, dry season", "onion", dict(ph=7.4, nitrogen=0.9, phosphorus=12, potassium=0.3, organic_carbon=0.6, ec=1.0, moisture=60, texture="sandy_loam"), "S2/S3"),
    ("Abeokuta, Ogun (kit readings only)", "tomato", dict(ph=6.5, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.5, moisture=65, texture="loam"), "S1"),
    ("Kaduna (after lime and compost)", "tomato", dict(ph=6.5, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="sandy_loam"), "S1"),
    ("Yobe (alkaline fadama)", "pepper", dict(ph=8.3, nitrogen=0.8, phosphorus=10, potassium=0.35, organic_carbon=0.4, ec=2.0, moisture=50, texture="sandy_loam"), "S3"),
    ("Boundary probe, pH 5.95", "tomato", dict(ph=5.95, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="loam"), "S1/S2"),
    ("Boundary probe, pH 6.05", "tomato", dict(ph=6.05, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="loam"), "S1"),
    ("Jos Plateau (heavy clay loam)", "onion", dict(ph=6.3, nitrogen=1.6, phosphorus=18, potassium=0.3, organic_carbon=1.4, ec=0.4, moisture=70, texture="clay_loam"), "S3"),
    ("Maiduguri outskirts (dry sand, no irrigation)", "tomato", dict(ph=7.0, nitrogen=0.5, phosphorus=6, potassium=0.2, organic_carbon=0.3, ec=1.5, moisture=20, texture="sandy"), "S3/N"),
    ("Input error: pH typed as 14", "tomato", dict(ph=14, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.0, moisture=65, texture="loam"), "N"),
]
# Expectations for these two were "N" before evaluation. They were revised to "S3" when the pH ratings
# were aligned with Sadiq et al. (2025), which rates pH beyond the S2 bands as S3, not N.
REVISED = {"Badagry, Lagos (fresh acid sand)": "N", "Yobe (alkaline fadama)": "N"}
R["scenarios"] = []
for name, crop, inp, exp in SCEN:
    r = evaluate(crop, inp)
    R["scenarios"].append({
        "name": name, "crop": crop, "inputs": inp, "expected": exp, "class": r["class"], "score": r["score"],
        "limiting": [f"{l['label']} ({l['term_label']})" for l in r["limiting"]],
        "notes": [f"{n['label']} ({n['term_label']})" for n in r["notes"]],
        "agree": r["class"] in exp.split("/"),
        "original_expected": REVISED.get(name),
    })
R["scenarios_agree"] = sum(s["agree"] for s in R["scenarios"])


# ------------------------------------------------------------------ 4. zones x crops
R["zones"] = {}
for z in K.ZONE_ORDER:
    R["zones"][z] = {}
    for c in K.CROP_ORDER:
        r = evaluate(c, K.ZONES[z]["preset"])
        R["zones"][z][c] = {"score": r["score"], "class": r["class"],
                            "top": r["limiting"][0]["label"] if r["limiting"] else (r["notes"][0]["label"] + " (note)" if r["notes"] else "")}


# ------------------------------------------------------------------ 5. comparative validation vs crisp
def crisp_class(crop, inp):
    """Crisp FAO/Sys reference: each factor takes the term with the highest membership
    (equivalent to sharp class limits at the 0.5 crossover); the plot takes the worst rating."""
    mu = fuzzify(crop, inp)
    ratings = K.rating_table(crop)
    worst = "S1"
    for f in K.FACTOR_ORDER:
        t = max(mu[f].items(), key=lambda kv: kv[1])[0]
        r = ratings[f][t]
        if WORST[r] > WORST[worst]:
            worst = r
    return worst


rng = np.random.default_rng(2026)
RANGES = dict(ph=(4.5, 8.0), nitrogen=(0.3, 2.8), phosphorus=(3, 35), potassium=(0.05, 0.6),
              organic_carbon=(0.2, 2.5), ec=(0.1, 5.0), moisture=(20, 110))
N_PER_CROP = 200
pairs = []
for c in K.CROP_ORDER:
    for _ in range(N_PER_CROP):
        inp = {f: round(float(rng.uniform(*RANGES[f])), 2) for f in RANGES}
        inp["texture"] = K.FACTORS["texture"]["classes"][int(rng.integers(5))]
        fz = evaluate(c, inp)
        pairs.append((c, fz["class"], crisp_class(c, inp), fz["score"], inp))

n = len(pairs)
cm = {a: {b: 0 for b in CLASS_ORDER} for a in CLASS_ORDER}   # rows: crisp, cols: fuzzy
for c, fz, cr, s, _ in pairs:
    cm[cr][fz] += 1
agree = sum(cm[k][k] for k in CLASS_ORDER)
po = agree / n
pe = sum((sum(cm[k].values()) / n) * (sum(cm[r][k] for r in CLASS_ORDER) / n) for k in CLASS_ORDER)
kappa = (po - pe) / (1 - pe)
within_one = sum(1 for _, fz, cr, _, _ in pairs if abs(WORST[fz] - WORST[cr]) <= 1) / n
by_crop = {}
for c in K.CROP_ORDER:
    sub = [p for p in pairs if p[0] == c]
    by_crop[c] = round(100 * sum(1 for p in sub if p[1] == p[2]) / len(sub), 1)
fuzzy_dist = {k: sum(1 for p in pairs if p[1] == k) for k in CLASS_ORDER}
crisp_dist = {k: sum(1 for p in pairs if p[2] == k) for k in CLASS_ORDER}

# Where do they disagree? Measure how close the disagreeing plots were to a class boundary:
def max_mixed_membership(crop, inp):
    mu = fuzzify(crop, inp)
    m = 0.0
    for f in K.FACTOR_ORDER:
        if f == "texture":
            continue
        vals = sorted(mu[f].values(), reverse=True)
        m = max(m, vals[1] if len(vals) > 1 else 0.0)  # second-largest membership: >0 means on a shoulder
    return m

def deciding_partial(crop, inp, cls):
    """True if a property that decided the crisp class is only partly in its winning term (i.e. near a class edge)."""
    mu = fuzzify(crop, inp); ratings = K.rating_table(crop)
    for f in K.FACTOR_ORDER:
        if f == "texture":
            continue
        t, m = max(mu[f].items(), key=lambda kv: kv[1])
        if ratings[f][t] == cls and m < 0.999:
            return True
    # also: a property whose partial membership in a worse-rated term could change the class
    for f in K.FACTOR_ORDER:
        if f == "texture":
            continue
        for t, m in mu[f].items():
            if 0.001 < m < 0.999 and WORST[ratings[f][t]] >= WORST[cls] and ratings[f][t] != max(mu[f].items(), key=lambda kv: kv[1])[0]:
                pass
    return False

def deciding_props(crop, inp, cls):
    mu = fuzzify(crop, inp); ratings = K.rating_table(crop); out = set()
    for f in K.FACTOR_ORDER:
        t = max(mu[f].items(), key=lambda kv: kv[1])[0]
        if ratings[f][t] == cls:
            out.add(f)
    return out

dis = [p for p in pairs if p[1] != p[2]]
agr = [p for p in pairs if p[1] == p[2]]
dis_on_shoulder = sum(1 for p in dis if deciding_partial(p[0], p[4], p[2]))
agr_on_shoulder = sum(1 for p in agr if deciding_partial(p[0], p[4], p[2]))
any_shoulder_all = sum(1 for p in pairs if max_mixed_membership(p[0], p[4]) >= 0.2)

# Limiting-factor agreement (Table 3.7, row 6): for plots the crisp reference puts in S3 or N, is the fuzzy
# system's top limiting factor one of the properties that set the crisp class?
lf_n = lf_ok = 0
for c, fz, cr, sc, inp in pairs:
    if cr in ("S3", "N"):
        res = evaluate(c, inp)
        if res["limiting"]:
            lf_n += 1
            lf_ok += res["limiting"][0]["factor"] in deciding_props(c, inp, cr)
fuzzy_lower = sum(1 for p in dis if WORST[p[1]] > WORST[p[2]])
fuzzy_higher = sum(1 for p in dis if WORST[p[1]] < WORST[p[2]])

R["validation"] = {
    "n": n, "per_crop": N_PER_CROP, "seed": 2026, "ranges": RANGES,
    "agreement_pct": round(100 * po, 1), "kappa": round(kappa, 3), "within_one_class_pct": round(100 * within_one, 1),
    "confusion_crisp_rows_fuzzy_cols": cm, "by_crop_pct": by_crop,
    "fuzzy_dist": fuzzy_dist, "crisp_dist": crisp_dist,
    "disagreements": len(dis), "disagreements_deciding_near_edge": dis_on_shoulder,
    "agreements": len(agr), "agreements_deciding_near_edge": agr_on_shoulder,
    "plots_any_property_on_shoulder": any_shoulder_all,
    "limiting_factor_agreement": {"plots": lf_n, "agree": lf_ok, "pct": round(100 * lf_ok / lf_n, 1) if lf_n else None},
    "fuzzy_stricter": fuzzy_lower, "fuzzy_more_lenient": fuzzy_higher,
}


# ------------------------------------------------------------------ 6. boundary sweeps
BASE = dict(nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="loam")
CRISP_SCORE = {"S1": 87.5, "S2": 62.5, "S3": 37.5, "N": 12.5}  # band midpoints, for plotting only

def sweep(crop, factor, values, base):
    out = []
    for v in values:
        inp = dict(base, **{factor: float(v)})
        inp.setdefault("ph", 6.5)
        fz = evaluate(crop, inp)
        out.append({"x": round(float(v), 3), "fuzzy": fz["score"], "fclass": fz["class"], "crisp": crisp_class(crop, inp)})
    return out

ph_vals = np.round(np.arange(4.0, 9.01, 0.05), 2)
ec_vals = np.round(np.arange(0.0, 8.01, 0.05), 2)
R["sweep_ph_tomato"] = sweep("tomato", "ph", ph_vals, BASE)
R["sweep_ec_onion"] = sweep("onion", "ec", ec_vals, dict(BASE, ph=6.5))

def max_step(sw):
    ys = [p["fuzzy"] for p in sw]
    return round(max(abs(b - a) for a, b in zip(ys, ys[1:])), 2)

def crisp_jumps(sw):
    return sum(1 for a, b in zip(sw, sw[1:]) if a["crisp"] != b["crisp"])

R["sweep_stats"] = {
    "ph_max_step_fuzzy": max_step(R["sweep_ph_tomato"]), "ph_step": 0.05, "ph_crisp_jumps": crisp_jumps(R["sweep_ph_tomato"]),
    "ec_max_step_fuzzy": max_step(R["sweep_ec_onion"]), "ec_step": 0.05, "ec_crisp_jumps": crisp_jumps(R["sweep_ec_onion"]),
}
# The score at the crisp jump points, e.g. pH 5.95 vs 6.05
R["boundary_pairs"] = {
    "ph_5.95": evaluate("tomato", dict(BASE, ph=5.95))["score"], "ph_6.05": evaluate("tomato", dict(BASE, ph=6.05))["score"],
    "ph_5.95_crisp": crisp_class("tomato", dict(BASE, ph=5.95)), "ph_6.05_crisp": crisp_class("tomato", dict(BASE, ph=6.05)),
}


# ------------------------------------------------------------------ 7. engine speed
inputs = [p[4] for p in pairs[:300]]
crops = [p[0] for p in pairs[:300]]
for c, i in zip(crops[:20], inputs[:20]):
    evaluate(c, i)  # warm-up
times = []
for c, i in zip(crops, inputs):
    t0 = time.perf_counter(); evaluate(c, i); times.append((time.perf_counter() - t0) * 1000)
times.sort()
R["engine_ms"] = {"n": len(times), "mean": round(statistics.mean(times), 2), "median": round(statistics.median(times), 2),
                  "p95": round(times[int(0.95 * len(times)) - 1], 2), "max": round(times[-1], 2)}

with open(os.path.join(OUT, "results.json"), "w") as fh:
    json.dump(R, fh, indent=1, default=float)

print("rules:", R["rules_total"], R["rules"])
print("MFs:", R["mf_count"])
print("scenarios agree:", R["scenarios_agree"], "/", len(SCEN))
print("validation:", {k: v for k, v in R["validation"].items() if k not in ("confusion_crisp_rows_fuzzy_cols", "ranges")})
print("confusion (rows crisp, cols fuzzy):"); [print(" ", k, R["validation"]["confusion_crisp_rows_fuzzy_cols"][k]) for k in CLASS_ORDER]
print("sweeps:", R["sweep_stats"], R["boundary_pairs"])
print("engine ms:", R["engine_ms"])
print("zones:"); [print(" ", z, {c: (v["class"], v["score"]) for c, v in R["zones"][z].items()}) for z in K.ZONE_ORDER]
