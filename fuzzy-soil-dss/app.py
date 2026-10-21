"""
Fuzzy-Based Decision Support System for Soil Selection in Vegetable Farming.
Flask application. Run: python app.py  (http://127.0.0.1:5000)
"""
from __future__ import annotations

import json
import os

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

import math

from engine import db, evaluate, mf_curves
from engine.fis import representative_values
from engine import knowledge as K

app = Flask(__name__)
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
db.init()


def _parse_inputs(payload):
    """Validate a form or JSON payload. Numbers only (no booleans, no NaN/inf), texture whitelisted."""
    inputs = {}
    errors = {}
    if not isinstance(payload, dict):
        payload = {}
    for f in K.FACTOR_ORDER:
        raw = payload.get(f)
        if f == "texture":
            if not isinstance(raw, str) or raw not in K.FACTORS["texture"]["classes"]:
                errors[f] = "choose a texture class"
            inputs[f] = raw if isinstance(raw, str) else None
            continue
        if isinstance(raw, bool) or raw is None:
            errors[f] = "enter a number"
            continue
        try:
            v = float(str(raw).strip().replace("_", "x")) if isinstance(raw, str) else float(raw)
        except (TypeError, ValueError):
            errors[f] = "enter a number"
            continue
        if not math.isfinite(v):
            errors[f] = "enter a number"
            continue
        lo, hi = K.FACTORS[f]["universe"]
        if not (lo <= v <= hi):
            errors[f] = f"must be between {lo:g} and {hi:g}"
        inputs[f] = v
    return inputs, errors


def _clean_crop(v):
    return v if isinstance(v, str) and v in K.CROPS else None


def _clean_state(v):
    return v if isinstance(v, str) and v in K.STATES else ""


def _json_payload():
    p = request.get_json(silent=True)
    return p if isinstance(p, dict) else {}


@app.context_processor
def inject_globals():
    return {
        "CROPS": K.CROPS, "CROP_ORDER": K.CROP_ORDER, "ZONES": K.ZONES, "ZONE_ORDER": K.ZONE_ORDER,
        "FACTORS": K.FACTORS, "FACTOR_ORDER": K.FACTOR_ORDER, "STATES": K.STATES,
    }


# ----------------------------------------------------------------------------- pages

@app.route("/")
def home():
    st = db.stats()
    return render_template("index.html", stats=st)


def _analyse_ctx(crop, state, **extra):
    zone = request.args.get("zone", "")
    ctx = {
        "crop": crop, "state": state,
        "zone": zone if zone in K.ZONES else "",
        "crop_json": json.dumps({k: {"name": v["name"], "accent": v["accent"]} for k, v in K.CROPS.items()}),
        "zones_json": json.dumps({k: {"name": v["name"], "preset": v["preset"], "notes": v["notes"], "palette": v["palette"]} for k, v in K.ZONES.items()}),
        "states_json": json.dumps(K.STATES),
        "factors_json": json.dumps({f: {k: v for k, v in K.FACTORS[f].items() if k != "mfs"} for f in K.FACTOR_ORDER}),
        "ratings_json": json.dumps({c: K.rating_table(c) for c in K.CROP_ORDER}),
        "rep_json": json.dumps({c: representative_values(c) for c in K.CROP_ORDER}),
        "default_json": json.dumps(K.ZONES["guinea"]["preset"]),
    }
    ctx.update(extra)
    return ctx


@app.route("/analyse")
def analyse():
    crop = _clean_crop(request.args.get("crop")) or "tomato"
    state = _clean_state(request.args.get("state"))
    # Values carried in the query string (e.g. "Adjust the values" from a result) pre-fill the form.
    values = None
    if any(f in request.args for f in K.FACTOR_ORDER):
        parsed, errs = _parse_inputs(request.args)
        if not errs:
            values = {f: (parsed[f] if f == "texture" else f"{parsed[f]:g}") for f in K.FACTOR_ORDER}
    return render_template("analyse.html", **_analyse_ctx(crop, state, values=values))


@app.route("/evaluate", methods=["POST"])
def evaluate_form():
    crop = _clean_crop(request.form.get("crop"))
    if not crop:
        abort(400)
    state = _clean_state(request.form.get("state"))
    inputs, errors = _parse_inputs(request.form)
    if errors:
        return render_template("analyse.html", **_analyse_ctx(crop, state, errors=errors, values=request.form)), 400
    result = evaluate(crop, inputs, rules=db.load_rules(crop))
    qid = db.log_query(crop, state, inputs, result)
    return redirect(url_for("result", qid=qid))


@app.route("/result/<qid>")
def result(qid):
    q = db.get_query(qid)
    if not q:
        abort(404)
    r = q["result"]
    crop = K.CROPS[q["crop_id"]]
    zone_key = K.STATES.get(q["state"])
    zone = K.ZONES.get(zone_key) if zone_key else None
    # Compare this plot against every crop so the farmer can see alternatives.
    alternatives = []
    for ck in K.CROP_ORDER:
        rr = evaluate(ck, q["inputs"], rules=db.load_rules(ck))
        alternatives.append({"key": ck, "name": K.CROPS[ck]["name"], "score": rr["score"], "class": rr["class"], "accent": K.CROPS[ck]["accent"]})
    alternatives.sort(key=lambda a: -a["score"])
    adjust_url = url_for("analyse", crop=q["crop_id"], state=q["state"], **{f: (q["inputs"][f] if f == "texture" else f"{q['inputs'][f]:g}") for f in K.FACTOR_ORDER})
    return render_template("result.html", q=q, r=r, crop=crop, zone=zone, alternatives=alternatives,
                           adjust_url=adjust_url, share_url=url_for("result", qid=qid, _external=True))


@app.route("/method")
def method():
    return render_template("method.html")


@app.route("/knowledge")
def knowledge():
    crop = request.args.get("crop", "tomato")
    if crop not in K.CROPS:
        crop = "tomato"
    rules = db.load_rules(crop)
    ratings = K.rating_table(crop)
    return render_template("knowledge.html", crop=crop, rules=rules, ratings=ratings, counts=db.rule_counts())


@app.route("/feedback/<qid>", methods=["POST"])
def feedback(qid):
    if not db.add_feedback(qid, request.form.get("helpful") == "yes", (request.form.get("comment") or "")[:500]):
        abort(404)
    return redirect(url_for("result", qid=qid) + "?thanks=1")


# ----------------------------------------------------------------------------- api

@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    payload = _json_payload()
    crop = _clean_crop(payload.get("crop"))
    if not crop:
        return jsonify({"errors": {"crop": "unknown crop; one of " + ", ".join(K.CROP_ORDER)}}), 400
    inputs, errors = _parse_inputs(payload)
    if errors:
        return jsonify({"errors": errors}), 400
    r = evaluate(crop, inputs, rules=db.load_rules(crop))
    if payload.get("log", True) is True:
        r["query_id"] = db.log_query(crop, _clean_state(payload.get("state")), inputs, r)
    return jsonify(r)


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Same as evaluate but never logged; used for live feedback on the form."""
    payload = _json_payload()
    crop = _clean_crop(payload.get("crop"))
    inputs, errors = _parse_inputs(payload)
    if not crop:
        errors["crop"] = "unknown crop"
    if errors:
        return jsonify({"errors": errors}), 400
    r = evaluate(crop, inputs, rules=db.load_rules(crop))
    return jsonify({"score": r["score"], "class": r["class"], "class_label": r["class_label"],
                    "memberships": r["memberships"], "limiting": r["limiting"][:3], "factor_scores": r["factor_scores"]})


@app.route("/api/crops")
def api_crops():
    return jsonify({k: {"name": v["name"], "scientific": v["scientific"], "ph": v["ph"], "ec": v["ec"]} for k, v in K.CROPS.items()})


@app.route("/api/zones")
def api_zones():
    return jsonify({"zones": K.ZONES, "states": K.STATES})


@app.route("/api/mf/<crop>/<factor>")
def api_mf(crop, factor):
    if crop not in K.CROPS or factor not in K.FACTORS or factor == "texture":
        abort(404)
    return jsonify(mf_curves(crop, factor))


@app.route("/api/rules/<crop>")
def api_rules(crop):
    if crop not in K.CROPS:
        abort(404)
    return jsonify(db.load_rules(crop))


@app.route("/api/representative/<crop>")
def api_representative(crop):
    if crop not in K.CROPS:
        abort(404)
    return jsonify(representative_values(crop))


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    return render_template("error.html", code=404, message="That page or result does not exist. Results expire only if the database is reset."), 404


@app.errorhandler(400)
def bad_request(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "bad request"}), 400
    return render_template("error.html", code=400, message="The request could not be understood. Go back and check the values."), 400


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "payload too large"}), 413


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "crops": len(K.CROPS), "rules": sum(db.rule_counts().values())})


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("DEBUG") == "1")
