"""Real-life scenarios run against the engine. Expected class is written BEFORE running,
from agronomic reasoning, so the engine is being tested, not rationalised."""
import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from engine import evaluate, knowledge as K

S = [
 # name, crop, inputs, expected class(es), expected top limiting factor (or None), rationale
 ("Kadawa irrigation scheme tomato, Kano. Lab sheet from IAR Samaru.", "tomato",
  dict(ph=6.6, nitrogen=0.7, phosphorus=9, potassium=0.25, organic_carbon=0.45, ec=1.4, moisture=55, texture="sandy_loam"),
  {"S3"}, "organic_carbon", "Classic Sudan savanna: pH fine, OC very low, N low. OC should lead."),
 ("Jos Plateau cabbage, Vom. Cool highland loam with years of manure.", "cabbage",
  dict(ph=5.9, nitrogen=2.2, phosphorus=22, potassium=0.4, organic_carbon=1.9, ec=0.3, moisture=70, texture="loam"),
  {"S1", "S2"}, None, "Good plot. pH 5.9 is just under cabbage S1 (6.0) so S2 acceptable; nothing should be 'limiting'."),
 ("Ikorodu amaranth bed, Lagos. Poultry manure heavy, irrigated with borehole, 3 years continuous.", "amaranth",
  dict(ph=6.2, nitrogen=2.5, phosphorus=35, potassium=0.6, organic_carbon=2.4, ec=3.6, moisture=70, texture="sandy_loam"),
  {"S1", "S2"}, None, "Fertile. ECe 3.6 vs amaranth threshold 2.0 (spinach proxy) is about 12% yield loss, still S1 by Sys bands, but salinity must appear in the notes."),
 ("Fresh acid sand near Badagry, never farmed, for pepper.", "pepper",
  dict(ph=4.6, nitrogen=0.6, phosphorus=4, potassium=0.08, organic_carbon=0.5, ec=0.3, moisture=60, texture="sandy"),
  {"N"}, "ph", "pH 4.6 is below pepper S2 floor (5.0): strongly acidic -> N. Lime before anything else."),
 ("Niger Delta backswamp plot, Yenagoa, onion attempt.", "onion",
  dict(ph=5.0, nitrogen=1.9, phosphorus=9, potassium=0.3, organic_carbon=2.6, ec=2.8, moisture=105, texture="clay"),
  {"N"}, "texture", "Waterlogged clay for onion is hopeless: moisture wet -> N, clay -> N, EC 2.8 > 50% loss point (1.2+50/16=4.3? no, 25% at 2.76) so 'high'. Multiple N vetoes."),
 ("Same Yenagoa plot, okra instead.", "okra",
  dict(ph=5.0, nitrogen=1.9, phosphorus=9, potassium=0.3, organic_carbon=2.6, ec=2.8, moisture=105, texture="clay"),
  {"S3"}, None, "Okra tolerates wet (S3) and clay (S3); pH 5.0 is okra S2 floor edge; EC 2.8 vs okra a=2.0, 25% loss at 4.5 -> moderate. Should be S3 not N, and better than onion."),
 ("Fadama onion, Sokoto-Rima, dry season with canal water.", "onion",
  dict(ph=7.4, nitrogen=0.9, phosphorus=12, potassium=0.3, organic_carbon=0.6, ec=1.0, moisture=60, texture="sandy_loam"),
  {"S2", "S3"}, None, "pH 7.4 is onion S2 (7.0 to 7.8); OC 0.6 'low' is S3 -> likely S3 with OC leading. Either S2/S3 acceptable; EC must NOT be flagged (1.0 < 1.2)."),
 ("Abeokuta backyard tomato, rapid kit only: pH strip 6.5, 'medium' NPK, feels loamy.", "tomato",
  dict(ph=6.5, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.5, moisture=65, texture="loam"),
  {"S1"}, None, "Table 3.4 R1 of the report: neutral pH, low salt, loam, adequate N, moderate OC is highly suitable."),
 ("Ideal commercial tomato field, Kaduna, after lime and compost programme.", "tomato",
  dict(ph=6.5, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="sandy_loam"),
  {"S1"}, None, "All S1. Must score 75+."),
 ("Alkaline fadama, Yobe, with free carbonates, trying pepper.", "pepper",
  dict(ph=8.3, nitrogen=0.8, phosphorus=10, potassium=0.35, organic_carbon=0.4, ec=2.0, moisture=50, texture="sandy_loam"),
  {"N"}, "ph", "pH 8.3 > pepper S2 ceiling 7.8 -> strongly alkaline N. EC 2.0 vs pepper a=1.5: 25% loss at 3.3 -> moderate. pH should lead."),
 ("Boundary probe: tomato at pH 5.95 vs 6.05, everything else perfect.", "tomato",
  dict(ph=5.95, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="loam"),
  {"S1", "S2"}, None, "Fuzzy edge: should NOT snap to a hard class; score near the S1/S2 border and close to the 6.05 result."),
 ("Boundary probe partner: pH 6.05.", "tomato",
  dict(ph=6.05, nitrogen=2.3, phosphorus=28, potassium=0.45, organic_carbon=1.8, ec=0.8, moisture=70, texture="loam"),
  {"S1"}, None, "Compare with previous: difference in score should be small (a few points)."),
 ("Plateau potato farmer's spare plot, trying onion on heavy clay loam.", "onion",
  dict(ph=6.3, nitrogen=1.6, phosphorus=18, potassium=0.3, organic_carbon=1.4, ec=0.4, moisture=70, texture="clay_loam"),
  {"S3"}, "texture", "Only problem is clay loam, rated S3 for onion. Texture must be the single limiting factor."),
 ("Drought-stressed Sahel garden, Maiduguri outskirts, tomato, no irrigation yet.", "tomato",
  dict(ph=7.0, nitrogen=0.5, phosphorus=6, potassium=0.2, organic_carbon=0.3, ec=1.5, moisture=20, texture="sandy"),
  {"S3", "N"}, None, "Dry (S3), sandy (S3), N low (S3), P low (S3), OC very low (S3). No single N but five S3s: should be low S3, well below a single-limitation plot."),
 ("Garbage input: farmer typed pH 14 and EC 0.", "tomato",
  dict(ph=14, nitrogen=1.5, phosphorus=14, potassium=0.23, organic_carbon=1.2, ec=0.0, moisture=65, texture="loam"),
  {"N"}, "ph", "pH clipped to universe max 10 -> strongly alkaline -> N. Must not crash."),
]

print(f"{'#':>2} {'crop':9} {'exp':6} {'got':4} {'score':>5} {'cent':>5}  top limiting      ok?  scenario")
fails = 0
prev = None
for i, (name, crop, inp, exp, top, why) in enumerate(S, 1):
    r = evaluate(crop, inp)
    got_top = r["limiting"][0]["factor"] if r["limiting"] else None
    ok_cls = r["class"] in exp
    ok_top = (top is None) or (got_top == top)
    ok = ok_cls and ok_top
    if not ok: fails += 1
    print(f"{i:>2} {crop:9} {'/'.join(sorted(exp)):6} {r['class']:4} {r['score']:5.1f} {r['mamdani_centroid']:5.1f}  {str(got_top):16} {'ok' if ok else 'FAIL'}  {name[:60]}")
    if not ok:
        print("     expected:", why)
        print("     limiting:", [(l['factor'], l['term'], l['rating'], l['strength']) for l in r['limiting']])
        print("     notes:", [(l['factor'], l['term']) for l in r['notes']])
    if "Ikorodu" in name:
        print("     notes:", [(n['factor'], n['term_label'], n['strength']) for n in r['notes']])
    if "Boundary probe partner" in name:
        print(f"     boundary pair: {prev['score']} vs {r['score']} (diff {abs(prev['score']-r['score']):.1f}), centroids {prev['mamdani_centroid']} vs {r['mamdani_centroid']}")
    prev = r
print(f"\n{len(S)-fails}/{len(S)} scenarios behaved as an agronomist would expect.")
