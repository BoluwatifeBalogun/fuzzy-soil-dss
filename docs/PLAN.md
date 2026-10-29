# Fuzzy-Based Decision Support System for Soil Selection in Vegetable Farming

Implementation plan. Case study: Nigeria as a whole, organised by agro-ecological zone.
This document is the engineering counterpart of Chapter Three of the seminar report.

---

## 1. What the system does, in one paragraph

A farmer or extension agent picks a vegetable crop (tomato, pepper, okra, onion, cabbage, amaranth), optionally picks their state so the form is pre-filled with the typical soil of that agro-ecological zone, enters or adjusts eight soil parameters, and gets back: a suitability score (0 to 100), the FAO class (S1 / S2 / S3 / N), the factors that are holding the plot back ranked by how hard they bite, and practical advice for each. Every answer comes with the rules that fired, so the reasoning can be inspected.

---

## 2. The algorithm

### 2.1 Mamdani fuzzy inference with "most limiting factor" rule structure

The engine is a Mamdani fuzzy inference system (Mamdani and Assilian, 1975) built on scikit-fuzzy's membership and defuzzification primitives. Rule evaluation is written explicitly (rather than hidden inside `skfuzzy.control`) so that firing strengths can be read back for the explanation.

Pipeline for one query:

```
crisp inputs  ->  fuzzify (per-crop membership functions)
              ->  evaluate rules (AND = min, OR = max, NOT = 1 - x)
              ->  clip each rule's consequent set by its firing strength
              ->  aggregate by max
              ->  centroid defuzzification  ->  score 0..100
              ->  map score to FAO class, extract limiting factors
```

### 2.2 Inputs (linguistic variables)

| # | Variable | Unit | Universe | Terms |
|---|----------|------|----------|-------|
| 1 | Soil pH (water) | pH | 3 to 10 | extremely acidic, strongly acidic, moderately acidic, neutral, moderately alkaline, strongly alkaline, extremely alkaline |
| 2 | Total nitrogen | g/kg | 0 to 5 | low, moderate, high |
| 3 | Available phosphorus (Bray-1) | mg/kg | 0 to 60 | low, moderate, high |
| 4 | Exchangeable potassium | cmol/kg | 0 to 2 | low, moderate, high |
| 5 | Organic carbon | % | 0 to 5 | very low, low, moderate, high |
| 6 | Electrical conductivity (ECe) | dS/m | 0 to 12 | low, moderate, high, very high |
| 7 | Soil moisture | % of field capacity | 0 to 120 (above 100 = waterlogged) | dry, moist, wet |
| 8 | Texture | class | sandy, sandy loam, loam, clay loam, clay | coarse, medium, fine (singleton membership) |

pH and ECe terms are **crop-specific**: their breakpoints are computed from each crop's published requirements. The remaining variables share breakpoints across crops (Nigerian laboratory conventions), with a per-crop *rating* of each term.

### 2.3 Where the breakpoints come from

* **pH**: Sadiq et al. (2025) for tomato (S1 = 6.0 to 7.0, S2 = 5.0 to 5.9 and 7.0 to 8.5). Other crops use provisional ranges from extension guidance, flagged in the knowledge base so an expert can edit them.
* **ECe**: Maas-Hoffman thresholds from FAO Irrigation and Drainage Paper 61 (Tanji and Kielen, 2002): tomato 2.5 dS/m, pepper 1.5, cabbage 1.8, onion 1.2, spinach 2.0 (proxy for amaranth). Okra has no published threshold and is treated as moderately sensitive (2.0, slope 10). From the threshold `a` and slope `b` (% yield loss per dS/m), term crossovers follow the Sys et al. (1991) limitation levels (85, 60 and 40 per cent of potential yield): low/moderate at 15% loss, moderate/high at 40%, high/very high at 60%. EC at loss L is `a + L / b`. Salinity above `a` but inside "low" is still reported to the user as a note with the estimated loss.
* **N, P, K, OC**: soil-test interpretation classes used by Nigerian laboratories, after Ogunleye et al. (2018) (total N: <1 g/kg low, 1 to 2 moderate, >2 high; Bray-1 P: <8 mg/kg low, 8 to 20 moderate, >20 high; K: <0.15 cmol/kg low, 0.15 to 0.30 moderate, >0.30 high; OC: <0.5% very low, 0.5 to 1.0 low, 1.0 to 1.5 moderate, >1.5 high, after Sys et al. 1993). Membership crosses 0.5 exactly at each class boundary and adjacent terms sum to 1 everywhere (a partition of unity), which the tests check on a 4,000-point grid for every crop and factor.
* **Ratings**: pH beyond the S2 bands (strongly acidic/alkaline) is S3, following Sadiq et al. (2025); pH below about 4.5 or above about 9.0 (extremely acidic/alkaline: aluminium toxicity, sodicity) is N (provisional); tomato/onion on clay or waterlogged soil are N; sandy texture, dry soil and near-absent organic carbon are S3; low N, P, K and low OC are S2 because fertility is a correctable limitation (Sys et al., 1991); moderate and high are S1.
* **Moisture / texture**: FAO (1976) and crop agronomy; onion and tomato are rated harder on heavy clay and waterlogging than amaranth and okra.

### 2.4 Rule generation (two tiers)

Writing a full factorial of 8 variables by hand is unmaintainable. The rule base is generated from each crop's *rating table*, where every (factor, term) pair carries a rating of S1, S2, S3 or N. Generation follows the FAO "most limiting factor" principle:

**Tier 1, limitation rules.** For each factor `f` and term `t`:

```
IF f IS t                                              THEN not_suitable          (if rated N)
IF f IS t AND NOT (any factor is in an N-rated term)   THEN marginally_suitable   (if rated S3)
```

**Tier 2, class rules.**

```
IF every factor is in an S1-rated term                                   THEN highly_suitable
IF every factor is in an S1- or S2-rated term AND some factor is in an S2 term  THEN moderately_suitable
```

Operators: AND = min, OR = max (within a factor and for "some factor"), NOT = 1 - x.

Consequences of this structure:

* A single N-rated factor at full membership fires a not_suitable rule at 1.0, silences every S3 rule through the guard, and pulls both tier-2 rules to 0. The centroid lands at 11.7. Liebig's law of the minimum, which is what agronomists expect.
* The guard matters: without it, an S3 rule firing beside an N rule adds output mass in the S3 region and *raises* the centroid (an audit found 11.7 becoming 22.8 when sandy texture was added to a saline plot). With it, adding a limitation can never raise the score; the tests check this for every factor on every crop.
* The "some factor is S2" condition on the moderate rule means N or S3 mass never lends support to "moderately suitable", which the earlier NOT(all S1) form allowed.
* A plot where everything is good fires highly_suitable at 1.0 and nothing else: score 88.3, the centroid of the S1 trapezoid.
* Partial memberships produce intermediate scores smoothly (tomato at pH 5.95 scores 84.9, at 6.05 scores 88.3).
* A plot with one S3 limitation and a plot with five both score 37.3: max-aggregation and the most-limiting-factor principle set the class from the worst factor alone. The result page lists every limiting factor and the per-factor chart shows the difference.
* The limiting factors are the tier-1 rules that fired, sorted by firing strength (N counted double), ties broken by how hard the factor is to correct: texture, moisture, pH, salinity, organic carbon, N, P, K.

Rule count per crop: one tier-1 rule per S3- or N-rated term plus 2 tier-2 rules (12 or 13 per crop; 76 in all). All rules are stored in SQLite as JSON with a `source` field, and are regenerated automatically whenever `knowledge.py` changes (a hash of the file is kept in the database).

### 2.5 Output variable and class mapping

| Term | Membership function (score) | Class | Score band |
|------|----------------------------|-------|-----------|
| not_suitable | trapezoid (0, 0, 15, 30) | N | 0 to 24 |
| marginally_suitable | triangle (20, 37, 55) | S3 | 25 to 49 |
| moderately_suitable | triangle (45, 62, 80) | S2 | 50 to 74 |
| highly_suitable | trapezoid (70, 85, 100, 100) | S1 | 75 to 100 |

### 2.6 Worked example (tomato)

Inputs: pH 5.6, N 1.2 g/kg, P 10 mg/kg, K 0.2 cmol/kg, OC 0.9%, ECe 1.0, moisture 65%, loam.

* pH 5.6 is 0.2 neutral / 0.8 moderately acidic (S2) for tomato.
* OC 0.9 is fully "low" (S2). N 1.2, P 10 and K 0.2 are fully moderate (S1).
* Everything else is S1.
* Fired: only the S2 class rule, at 0.8 (every factor is at least S2 at 0.8, the pH minimum; pH and OC supply the S2 mass). The S1 rule is 0 because OC has no S1 membership.
* Centroid 62.3: **S2, moderately suitable**. No limiting factors; notes: pH moderately acidic, organic carbon low. Advice: lime at 1 to 2 t/ha, 5 to 10 t/ha manure or compost.

Second example, the report's Table 3.4 rule R1 plot (pH 6.5, N 1.5, P 14, K 0.23, OC 1.2, ECe 0.5, 65%, loam): every factor is in an S1 term, score 88.3, **S1**.

---

## 3. Nigeria-wide case study: agro-ecological zones

The form can be pre-filled by state. Each state is mapped to one of six zones, and each zone carries a "typical plot" preset (a representative, not a measured, profile; the user adjusts it):

| Zone | Representative states | Typical soil sketch |
|------|-----------------------|---------------------|
| Sahel | Borno (north), Yobe, Jigawa (north), Sokoto (north), Katsina (north) | sandy, pH 6.5 to 7.5, very low OC, EC can be elevated, dry |
| Sudan savanna | Kano, Katsina, Sokoto, Zamfara, Kebbi, Jigawa, Bauchi (north), Gombe | sandy loam, pH 6.0 to 7.0, low OC and N, moderate K |
| Guinea savanna (northern and southern) | Kaduna, Niger, Kwara, Plateau, Nasarawa, FCT, Benue, Kogi, Taraba, Adamawa | sandy loam to loam, pH 5.5 to 6.5, low to moderate OC |
| Derived savanna | Oyo, Osun (north), Ekiti, Kogi (south), Enugu (north), Ebonyi | loam to clay loam, pH 5.5 to 6.5, moderate OC |
| Humid forest | Lagos, Ogun, Ondo, Edo, Delta (north), Imo, Abia, Anambra, Enugu (south), Cross River, Akwa Ibom | sandy loam, pH 4.8 to 6.0 (acidic), moderate OC, moist |
| Coastal / mangrove | Lagos (coast), Bayelsa, Rivers, Delta (south), Akwa Ibom (coast) | silty clay to clay, pH 4.5 to 6.0, high OC, wet, EC elevated |

These presets are a teaching and onboarding aid. The engine always evaluates the actual values on the form.

---

## 4. System architecture

```
browser (vanilla JS, no build step)
   |  HTML forms + fetch('/api/evaluate')
   v
Flask 3.1 app (app.py: page routes, JSON API)
   |  engine.evaluate(crop, inputs, rules)
   v
engine/  (fis.py, knowledge.py, db.py)            <- scikit-fuzzy 0.5.0 + numpy + scipy
   |  rules from SQLite; membership parameters and ratings from knowledge.py
   v
SQLite (soil.db): crops, rules, zones, states, query_log, feedback, meta
```

Pages:

1. `/` landing: hero, how it works, crops, zones, numbers, CTA
2. `/analyse` the form: crop picker, state/zone preset, eight inputs with live linguistic feedback, and a "no number? pick roughly" control per numeric input that sets a typical value for low / moderate / high
3. `/result/<id>` score gauge, FAO class, radar of factor suitability, limiting factors with advice, fired rules, membership plots, print / share
4. `/method` the fuzzy pipeline explained with live, interactive membership functions
5. `/knowledge` the crop profiles and generated rule base, with sources, searchable
6. `/api/evaluate`, `/api/preview` (never logged), `/api/crops`, `/api/zones`, `/api/mf/<crop>/<factor>`, `/api/rules/<crop>`, `/api/representative/<crop>`, `/healthz`

Editing the knowledge base is done in `engine/knowledge.py` (one rating table and one requirement block per crop); the rule base regenerates on the next start. An administrator page with accounts is future work.

---

## 5. Design system

Generated with the ui-ux-pro-max skill for "agriculture soil farming decision support Nigeria", then adjusted:

* Style: **Organic biophilic, editorial**. Warm off-white paper, deep forest green, harvest gold accent, laterite red for warnings (Nigerian soil colour, used sparingly), charcoal text. Full dark mode.
* Type: **Fraunces** (display serif, optical sizing, used large and tight) + **Inter** (UI) + **JetBrains Mono** (numbers, units, rule text). Big editorial headlines, generous line-height on body.
* Shape: 20 to 28 px radii on cards, pill buttons, a soft grain texture over the hero gradient.
* Motion (prefers-reduced-motion respected everywhere):
  * hero headline reveal by word (CSS, staggered)
  * scroll reveals via IntersectionObserver, 500 to 700 ms, expo-out curve
  * card hover: translateY(-4px), scale 1.02, shadow bloom, 250 ms
  * number tickers on the stats row
  * crop marquee (CSS keyframes, duplicated track)
  * gauge needle and radar polygon animate in with a cubic-bezier draw
  * sliders push live membership "pills" that fade/slide as the value crosses a breakpoint
  * magnetic primary button (pointer-follow within 24 px)
* Accessibility: labels on every input, 4.5:1 contrast, visible focus rings, keyboard reachable sliders and segmented controls, class badges carry text not just colour, SVG icons only (no emoji).
* Responsive breakpoints: 375, 768, 1024, 1440.

---

## 6. Work plan

| Step | Deliverable | Checks |
|------|-------------|--------|
| 1 | `engine/` with knowledge tables, MF builders, rule generator, inference, explanation | pytest: partition of unity on every factor and crop, universe end points, monotonicity in every factor, adding a limitation never raises the score, hand-calculated centroid, worked example, veto behaviour, every zone preset runs |
| 2 | SQLite schema + seed script | DB has 6 crops, 76 rules, 6 zones, 37 states; rules reseed when knowledge.py changes |
| 3 | Flask app + API | Flask test client: pages render, form round trip, validation re-render, malformed JSON returns 400 not 500, feedback needs a real query, 20 previews average under 0.2 s |
| 4 | Templates + CSS + JS | screenshots at 1440 / 375 on all pages, light and dark |
| 5 | Methodology + knowledge pages | interactive MF plot works without network |
| 6 | README, run instructions, packaging | `pip install -r requirements.txt && python app.py` from a clean folder |

Out of scope for this build (future work, per Chapter Three): expert validation on 40 real samples, SUS testing with farmers, an administrator page with accounts, Hausa / Yoruba / Igbo localisation, USSD channel.

## 7. Changes made during evaluation (Chapter Four)

* pH ratings were stricter than the cited source: strongly acidic/alkaline was rated N, so the Humid forest preset (Lagos, Ogun) returned "not suitable" for amaranth, onion and cabbage. Sadiq et al. (2025) rate pH beyond the S2 bands as S3. pH now has seven terms; the two outer ones (below about 4.5, above about 9.0) are N.
* Hint text colour failed WCAG 4.5:1 in light mode (3.3:1); darkened to #69615A (5.3:1).
* Result panels overflowed by 2 px at 375 px; fixed with min-width: 0 on grid children.
* After a validation error the Zone label lost the selected state; fixed.
* Result panels stretched to the height of the neighbouring panel; now aligned to the top.
* Salinity crossovers moved from 20/40/60 to 15/40/60 per cent yield loss to match the Sys et al. (1991) limitation levels (85/60/40 per cent of potential yield).
* Extreme-pH rules now cite the extreme-band source; query_log.crop_id and feedback.query_id declared as foreign keys.
* "Worth watching" notes said "moderate, not limiting" under a factor labelled "low"; now say "rated S2, correctable, not limiting".

Evaluation is reproducible with `python tests/evaluate_system.py` (writes docs/evaluation/results.json).

## 8. Deploying

`render.yaml` and `Procfile` are included. Push to GitHub, create a Render Blueprint from the repository, and it builds with gunicorn. Uncomment the disk block in `render.yaml` to keep the query log across deploys.
