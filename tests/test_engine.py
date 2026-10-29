import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402

from engine import evaluate, fuzzify, generate_rules, knowledge as K  # noqa: E402
from engine.fis import ph_mfs, ec_mfs, classify  # noqa: E402

GOOD = {"ph": 6.5, "nitrogen": 2.5, "phosphorus": 30, "potassium": 0.5, "organic_carbon": 2.0, "ec": 0.5, "moisture": 70, "texture": "loam"}


def test_ph_breakpoints_follow_sadiq_for_tomato():
    m = ph_mfs("tomato")
    assert m["neutral"][1][1:3] == (6.0, 7.0)
    assert m["moderately_acidic"][1][1] == 5.0
    assert m["moderately_alkaline"][1][2] == 8.5


def test_ec_breakpoints_from_maas_hoffman_and_sys_yield_bands():
    """Crossovers sit at 15, 40 and 60 % yield loss (Sys et al. 1991 limitation levels 85/60/40 % of potential yield)."""
    m = ec_mfs("onion")
    a, b = 1.2, 16.0
    e15, e40, e60 = a + 15 / b, a + 40 / b, a + 60 / b
    assert (m["low"][1][2] + m["low"][1][3]) / 2 == pytest.approx(e15)
    assert (m["moderate"][1][2] + m["moderate"][1][3]) / 2 == pytest.approx(e40)
    assert (m["high"][1][2] + m["high"][1][3]) / 2 == pytest.approx(e60)
    assert fuzzify("onion", dict(GOOD, ec=1.0))["ec"]["low"] == 1.0


def test_memberships_sum_sensibly():
    mu = fuzzify("tomato", GOOD)
    for f, terms in mu.items():
        assert 0.99 <= sum(terms.values()) <= 1.01, f


def test_ideal_plot_is_highly_suitable():
    for crop in K.CROP_ORDER:
        r = evaluate(crop, GOOD)
        assert r["class"] == "S1", (crop, r["score"])
        assert r["limiting"] == []


def test_single_veto_factor_gives_not_suitable():
    bad = dict(GOOD, ec=9.0)
    r = evaluate("tomato", bad)
    assert r["class"] == "N"
    assert r["limiting"][0]["factor"] == "ec"


def test_single_s3_factor_gives_marginal():
    r = evaluate("tomato", dict(GOOD, texture="sandy"))
    assert r["class"] == "S3"
    assert r["limiting"][0]["factor"] == "texture"


def test_all_s2_gives_moderate():
    s2 = {"ph": 5.5, "nitrogen": 1.5, "phosphorus": 14, "potassium": 0.23, "organic_carbon": 1.3, "ec": 3.5, "moisture": 70, "texture": "clay_loam"}
    r = evaluate("tomato", s2)
    assert r["class"] == "S2"


def test_worked_example_from_plan():
    ex = {"ph": 5.6, "nitrogen": 1.2, "phosphorus": 10, "potassium": 0.2, "organic_carbon": 0.9, "ec": 1.0, "moisture": 65, "texture": "loam"}
    r = evaluate("tomato", ex)
    assert r["class"] == "S2"
    assert r["limiting"] == []
    assert [n["factor"] for n in r["notes"]][:2] == ["ph", "organic_carbon"]


def test_score_monotone_in_ph_towards_neutral():
    scores = [evaluate("tomato", dict(GOOD, ph=p))["score"] for p in (4.0, 4.8, 5.3, 5.8, 6.5)]
    assert scores == sorted(scores)


def test_rule_base_size_and_sources():
    for crop in K.CROP_ORDER:
        rules = generate_rules(crop)
        assert 9 <= len(rules) <= 20
        assert all(r["source"] for r in rules)
        assert sum(1 for r in rules if r["tier"] == 2) == 2


def test_zone_presets_all_evaluate():
    for z in K.ZONE_ORDER:
        for crop in K.CROP_ORDER:
            r = evaluate(crop, K.ZONES[z]["preset"])
            assert r["class"] in ("S1", "S2", "S3", "N")


def test_classify_bands():
    assert classify(90)[0] == "S1"
    assert classify(74.9)[0] == "S2"
    assert classify(30)[0] == "S3"
    assert classify(5)[0] == "N"


# ---------------------------------------------------------------- audit-driven tests

import numpy as np
from engine.fis import factor_mfs, _mf, generate_rules as _gen


def test_every_numeric_factor_partitions_its_universe_for_every_crop():
    """Memberships of adjacent terms sum to 1 on a fine grid, including the end points."""
    for crop in K.CROP_ORDER:
        for f in K.FACTOR_ORDER:
            if f == "texture":
                continue
            lo, hi = K.FACTORS[f]["universe"]
            x = np.linspace(lo, hi, 4001)
            total = sum(_mf(k, p, x) for k, p in factor_mfs(crop, f).values())
            assert np.allclose(total, 1.0, atol=1e-6), (crop, f, float(total.min()), float(total.max()))


def test_universe_end_points_are_not_dead():
    for crop in K.CROP_ORDER:
        for f in K.FACTOR_ORDER:
            if f == "texture":
                continue
            for v in K.FACTORS[f]["universe"]:
                mu = fuzzify(crop, dict(GOOD, **{f: v}))[f]
                assert abs(sum(mu.values()) - 1.0) < 1e-6, (crop, f, v, mu)


def test_out_of_universe_value_is_clipped_not_dropped():
    r = evaluate("tomato", dict(GOOD, ph=14))
    assert r["class"] == "N" and r["limiting"][0]["factor"] == "ph"


def test_adding_a_limitation_never_raises_the_score():
    base = evaluate("tomato", dict(GOOD, ec=9.0))["score"]
    worse = evaluate("tomato", dict(GOOD, ec=9.0, texture="sandy"))["score"]
    assert worse <= base + 1e-9
    base = evaluate("onion", dict(GOOD, texture="clay"))["score"]
    worse = evaluate("onion", dict(GOOD, texture="clay", nitrogen=0.1))["score"]
    assert worse <= base + 1e-9


def test_score_monotone_in_every_factor():
    """Moving any factor from its worst value towards its best never lowers the score."""
    paths = {
        "ph": [3.5, 4.5, 5.0, 5.5, 6.0, 6.5], "nitrogen": [0.1, 0.7, 1.0, 1.5, 2.5],
        "phosphorus": [1, 6, 10, 16, 30], "potassium": [0.02, 0.1, 0.15, 0.25, 0.5],
        "organic_carbon": [0.1, 0.4, 0.7, 1.0, 1.3, 2.0], "ec": [8, 6, 4, 2.5, 1.0, 0.3],
        "moisture": [5, 25, 40, 55, 70], "texture": ["clay", "clay_loam", "loam"],
    }
    for crop in K.CROP_ORDER:
        for f, path in paths.items():
            scores = [evaluate(crop, dict(GOOD, **{f: v}))["score"] for v in path]
            assert all(b >= a - 1e-9 for a, b in zip(scores, scores[1:])), (crop, f, scores)


def test_moderate_rule_needs_s2_mass_not_just_absence_of_s1():
    """Waterlogging (an N term) must not lend support to 'moderately suitable'."""
    r = evaluate("tomato", dict(GOOD, moisture=91.5))
    fired = {fr["rule_id"]: fr["strength"] for fr in r["fired_rules"]}
    assert "TOM-C02" not in fired


def test_centroid_matches_hand_calculation_for_single_rule():
    """Only the S1 rule fires at strength 1: centroid of trapezoid (70,85,100,100)."""
    r = evaluate("tomato", GOOD)
    assert len(r["fired_rules"]) == 1
    # area = triangle 70..85 (7.5) + rectangle 85..100 (15); x = (7.5*80 + 15*92.5) / 22.5
    assert r["score"] == pytest.approx((7.5 * 80 + 15 * 92.5) / 22.5, abs=0.2)


def test_score_class_consistency_over_random_inputs():
    rng = np.random.default_rng(1)
    for _ in range(300):
        crop = K.CROP_ORDER[rng.integers(6)]
        inp = {f: (K.FACTORS[f]["classes"][rng.integers(5)] if f == "texture" else float(rng.uniform(*K.FACTORS[f]["universe"]))) for f in K.FACTOR_ORDER}
        r = evaluate(crop, inp)
        assert classify(r["score"])[0] == r["class"]
        assert not ({l["factor"] for l in r["limiting"]} & {n["factor"] for n in r["notes"]})
        if r["class"] in ("S3", "N"):
            assert r["limiting"], (crop, inp)
        for l in r["limiting"] + r["notes"]:
            assert l["advice"]


def test_rules_carry_n_guard_on_s3_rules():
    for crop in K.CROP_ORDER:
        for r in _gen(crop):
            if r["tier"] == 1 and r["consequent"] == "marginally_suitable":
                assert "not_any" in r


def test_report_table_3_4_rule_1_is_highly_suitable():
    """Neutral pH, low salt, loam, adequate N, moderate OC: the report's flagship example."""
    r = evaluate("tomato", {"ph": 6.5, "nitrogen": 1.5, "phosphorus": 14, "potassium": 0.23, "organic_carbon": 1.2, "ec": 0.5, "moisture": 65, "texture": "loam"})
    assert r["class"] == "S1"



def test_extreme_ph_rules_cite_the_extreme_band_source_and_keep_ph_capitalised():
    for crop in K.CROP_ORDER:
        for r in generate_rules(crop):
            if r["antecedent"].get("ph") and r["antecedent"]["ph"][0].startswith("extremely"):
                assert r["source"] == K.PH_EXTREME["source"]
                assert "soil pH" in r["text"]


def test_requirements_declare_scipy():
    """scikit-fuzzy 0.5.0 imports SciPy without declaring it (defect 1 in Chapter Four)."""
    import os
    req = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")).read().lower()
    assert "scipy" in req


def test_ph_beyond_s2_band_is_marginal_and_extremes_not_suitable():
    """Defect 9: pH beyond the S2 band rates S3 (Sadiq et al., 2025); below ~4.5 or above ~9 rates N."""
    from engine.fis import fuzzify
    r = K.rating_table("amaranth")["ph"]
    assert r["strongly_acidic"] == "S3" and r["strongly_alkaline"] == "S3"
    assert r["extremely_acidic"] == "N" and r["extremely_alkaline"] == "N"
    lagos = K.ZONES["forest"]["preset"]          # pH 5.2
    assert evaluate("amaranth", lagos)["class"] == "S3"
    assert evaluate("tomato", dict(GOOD, ph=3.8))["class"] == "N"
