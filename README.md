# Fuzzy-Based Decision Support System for Soil Selection in Vegetable Farming

Implementation of the seminar project by Nwokocha Jean Chukwuebuka (Department of Computer Technology, Yaba College of Technology). Case study: Nigeria, organised by agro-ecological zone.

A farmer or extension agent picks a vegetable (tomato, pepper, okra, onion, cabbage or amaranth), optionally picks a state to pre-fill the typical soil of that zone, enters eight soil parameters, and receives a suitability score (0 to 100), the FAO class (S1 / S2 / S3 / N), the limiting factors ranked by severity, practical advice, and the rules that fired.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The SQLite database (`soil.db`) is created and seeded on first run.

Tests:

```bash
python -m pytest -q
```

## What is where

| Path | Purpose |
|------|---------|
| `engine/knowledge.py` | Crop requirements, factor definitions, ratings, zone presets, advice. Every number has a source line. |
| `engine/fis.py` | Membership functions (scikit-fuzzy), rule generation, Mamdani inference, explanation. |
| `engine/db.py` | SQLite schema, seeding, query log, feedback. |
| `app.py` | Flask routes and JSON API. |
| `templates/`, `static/` | Front-end (vanilla HTML, CSS, JS; no build step). |
| `tests/test_engine.py` | Engine tests, including the worked example from the plan. |
| `docs/PLAN.md` | Algorithm, architecture, design system and work plan. |

## API

```
POST /api/evaluate   {"crop":"tomato","ph":5.6,"nitrogen":1.2,"phosphorus":10,"potassium":0.2,
                      "organic_carbon":0.9,"ec":1.0,"moisture":65,"texture":"loam","state":"Lagos"}
POST /api/preview    same body, never logged
GET  /api/crops      crop profiles
GET  /api/zones      zone presets and state mapping
GET  /api/mf/<crop>/<factor>   sampled membership curves
GET  /api/rules/<crop>         the stored rule base
```

## Pages

* `/` landing
* `/analyse` the form, with live fuzzy feedback as you drag
* `/result/<id>` the assessment, printable and shareable
* `/method` how the inference works, with an interactive membership explorer
* `/knowledge` the rating tables and generated rules for every crop

## Method in brief

Mamdani fuzzy inference. pH and salinity membership functions are crop-specific, derived from Sadiq et al. (2025) and the FAO Maas-Hoffman salt tolerance tables with Sys yield bands. The rule base is generated from a per-crop rating table following the FAO most-limiting-factor principle: one limitation rule per S3- or N-rated term (S3 rules guarded so a second problem never raises the score) plus 2 class rules per crop. The centroid of the aggregated output is the score and fixes the FAO class. See `docs/PLAN.md`.

## Deploy

`render.yaml` and `Procfile` are included for Render (gunicorn). See `docs/PLAN.md` section 7.

## Known limits

* Breakpoints marked "provisional" in the knowledge base come from extension guidance and need a soil scientist's review (planned in Chapter Three of the report).
* Zone presets are representative sketches, not measured values.
* No authentication; the feedback and query log are for calibration during validation.
