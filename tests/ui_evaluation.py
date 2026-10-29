"""
Screenshots and usability measurements for Chapter Four.

Start the server first (gunicorn app:app --workers 2 --threads 4 --bind 127.0.0.1:5000, or python app.py),
then run:  python tests/ui_evaluation.py
Needs: pip install playwright && playwright install chromium
Optional: set FONTS_DIR to a node_modules folder containing @fontsource-variable/fraunces, @fontsource/manrope
and @fontsource/ibm-plex-mono to capture with the production fonts when Google Fonts is unreachable.
Writes docs/evaluation/ui_metrics.json and screenshots to docs/evaluation/screens/.
"""
import json, os, statistics, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(ROOT, "docs", "evaluation")
FIG = os.path.join(OUTD, "screens"); os.makedirs(FIG, exist_ok=True)
FONTS = os.environ.get("FONTS_DIR", "")
FONT_FILES = {
    "fraunces-n.woff2": f"{FONTS}/@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2",
    "fraunces-i.woff2": f"{FONTS}/@fontsource-variable/fraunces/files/fraunces-latin-full-italic.woff2",
    **{f"manrope-{w}.woff2": f"{FONTS}/@fontsource/manrope/files/manrope-latin-{w}-normal.woff2" for w in (400, 500, 600, 700)},
    **{f"plex-{w}.woff2": f"{FONTS}/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-{w}-normal.woff2" for w in (400, 500)},
}
CSS = """
@font-face{font-family:'Fraunces';font-style:normal;font-weight:100 900;font-display:block;src:url(https://fonts.gstatic.com/x/fraunces-n.woff2) format('woff2-variations');}
@font-face{font-family:'Fraunces';font-style:italic;font-weight:100 900;font-display:block;src:url(https://fonts.gstatic.com/x/fraunces-i.woff2) format('woff2-variations');}
""" + "".join(f"@font-face{{font-family:'Manrope';font-weight:{w};font-display:block;src:url(https://fonts.gstatic.com/x/manrope-{w}.woff2) format('woff2');}}" for w in (400, 500, 600, 700)) \
    + "".join(f"@font-face{{font-family:'IBM Plex Mono';font-weight:{w};font-display:block;src:url(https://fonts.gstatic.com/x/plex-{w}.woff2) format('woff2');}}" for w in (400, 500))


def route_fonts(ctx):
    if not FONTS:
        return
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
    def gs(r):
        name = r.request.url.rsplit("/", 1)[-1]
        p = FONT_FILES.get(name)
        if p and os.path.exists(p):
            r.fulfill(status=200, content_type="font/woff2", body=open(p, "rb").read())
        else:
            r.fulfill(status=404, body="")
    ctx.route("https://fonts.gstatic.com/**", gs)


def settle(page, ms=1800):
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(ms)


def unstick(page):
    page.add_style_tag(content=".nav{position:relative !important}")
    page.wait_for_timeout(150)


def reveal_all(page):
    page.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'))")
    page.wait_for_timeout(500)


M = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
    route_fonts(ctx)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))

    # ---------------------------------------------------------------- screenshots, desktop
    pg.goto(BASE + "/"); settle(pg, 2600)
    pg.screenshot(path=f"{FIG}/s01_home_hero.png")
    reveal_all(pg)
    pg.locator(".crops").screenshot(path=f"{FIG}/s02_home_crops.png")
    pg.locator(".zones").screenshot(path=f"{FIG}/s03_home_zones.png")

    pg.goto(BASE + "/analyse"); settle(pg)
    pg.select_option("#state", "Lagos"); pg.wait_for_timeout(1400)
    pg.screenshot(path=f"{FIG}/s04_analyse_top.png")
    pg.evaluate("window.scrollTo(0, document.querySelector('#params').getBoundingClientRect().top + window.scrollY - 90)"); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{FIG}/s05_analyse_params.png")
    # rough-level mode: organic carbon -> very low
    pg.select_option("select[data-rough=organic_carbon]", "very_low"); pg.wait_for_timeout(1200)
    unstick(pg)
    pg.locator(".param[data-factor=organic_carbon]").screenshot(path=f"{FIG}/s06_rough_mode.png")
    pg.locator(".readout").screenshot(path=f"{FIG}/s07_live_readout.png")

    # validation error state: blank pH then submit (form has novalidate, server re-renders)
    pg.fill("#in-ph", "")
    pg.click("button[type=submit]"); settle(pg, 900)
    M["validation_status_text"] = pg.locator(".err").first.inner_text() if pg.locator(".err").count() else None
    M["zone_label_after_validation"] = pg.locator("#zoneLabel").inner_text()   # defect 12: must still name the zone
    pg.evaluate("document.querySelector('.err').scrollIntoView({block:'center'})"); pg.wait_for_timeout(500)
    pg.screenshot(path=f"{FIG}/s08_validation.png")

    # result page from the Kadawa scenario, via the real form
    pg.goto(BASE + "/analyse?crop=tomato&state=Kano&ph=6.6&nitrogen=0.7&phosphorus=9&potassium=0.25&organic_carbon=0.45&ec=1.4&moisture=55&texture=sandy_loam"); settle(pg)
    pg.click("button[type=submit]"); settle(pg, 2400)
    kadawa_url = pg.url
    pg.screenshot(path=f"{FIG}/s09_result_hero.png")
    unstick(pg)
    panels = pg.locator(".panel")
    panels.nth(0).screenshot(path=f"{FIG}/s10_result_limits.png")
    panels.nth(1).screenshot(path=f"{FIG}/s11_result_factors.png")
    panels.nth(2).screenshot(path=f"{FIG}/s12_result_crops.png")
    panels.nth(3).screenshot(path=f"{FIG}/s13_result_reasoning.png")

    # Yenagoa onion (N) result for contrast
    pg.goto(BASE + "/analyse?crop=onion&state=Bayelsa&ph=5.0&nitrogen=1.9&phosphorus=9&potassium=0.3&organic_carbon=2.6&ec=2.8&moisture=105&texture=clay"); settle(pg)
    pg.click("button[type=submit]"); settle(pg, 2400)
    pg.screenshot(path=f"{FIG}/s14_result_not_suitable.png")

    pg.goto(BASE + "/method"); settle(pg)
    pg.select_option("#mfCrop", "onion"); pg.wait_for_timeout(900); pg.select_option("#mfFactor", "ec"); pg.wait_for_timeout(1200)
    pg.evaluate("const v=document.getElementById('mfVal'); v.value='3.2'; v.dispatchEvent(new Event('input'))"); pg.wait_for_timeout(700)
    M["mf_probe_label"] = pg.locator("#mfValOut").inner_text()
    unstick(pg)
    pg.locator("#mfplot").screenshot(path=f"{FIG}/s15_method_explorer.png")
    pg.screenshot(path=f"{FIG}/s16_method_top.png")

    pg.goto(BASE + "/knowledge?crop=tomato"); settle(pg)
    pg.screenshot(path=f"{FIG}/s17_knowledge.png")

    pg.goto(BASE + "/result/doesnotexist"); settle(pg, 600)
    pg.screenshot(path=f"{FIG}/s18_not_found.png")

    # dark mode
    dctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5, color_scheme="dark")
    route_fonts(dctx)
    dp = dctx.new_page()
    dp.goto(BASE + "/analyse?zone=sudan"); settle(dp)
    dp.screenshot(path=f"{FIG}/s19_dark_analyse.png")
    dp.goto(kadawa_url); settle(dp, 2400)
    dp.screenshot(path=f"{FIG}/s20_dark_result.png")
    dctx.close()

    # mobile
    mctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    route_fonts(mctx)
    mp = mctx.new_page()
    mp.goto(BASE + "/"); settle(mp, 2400); mp.screenshot(path=f"{FIG}/m1_home.png")
    mp.goto(BASE + "/analyse?zone=forest"); settle(mp)
    mp.evaluate("window.scrollTo(0, document.querySelector('#params').getBoundingClientRect().top + window.scrollY - 70)"); mp.wait_for_timeout(700)
    mp.screenshot(path=f"{FIG}/m2_analyse.png")
    mp.goto(kadawa_url); settle(mp, 2400); mp.screenshot(path=f"{FIG}/m3_result.png")
    mctx.close()

    # ---------------------------------------------------------------- usability criteria
    # U1. Task completion and interaction count, pointer path (state preset -> result)
    tasks = []
    def run_task(name, steps):
        t = b.new_context(viewport={"width": 1440, "height": 900}); route_fonts(t); q = t.new_page()
        q.goto(BASE + "/analyse"); settle(q, 600)
        t0 = time.perf_counter(); n = 0
        for s in steps:
            s(q); n += 1
        q.wait_for_url("**/result/**", timeout=8000); q.wait_for_load_state("load")
        dt = time.perf_counter() - t0
        ok = q.locator(".verdict .badge").count() == 1
        tasks.append({"task": name, "interactions": n, "completed": ok, "system_time_s": round(dt, 2)})
        t.close()
    run_task("Assess tomato on a Lagos plot using the state preset", [
        lambda q: q.click("label:has(input[value=tomato])"),
        lambda q: (q.select_option("#state", "Lagos"), q.wait_for_timeout(300)),
        lambda q: q.click("button[type=submit]"),
    ])
    run_task("Assess onion from a laboratory sheet (eight values typed)", [
        lambda q: q.click("label:has(input[value=onion])"),
        lambda q: q.fill("#in-ph", "7.4"), lambda q: q.fill("#in-nitrogen", "0.9"), lambda q: q.fill("#in-phosphorus", "12"),
        lambda q: q.fill("#in-potassium", "0.3"), lambda q: q.fill("#in-organic_carbon", "0.6"), lambda q: q.fill("#in-ec", "1.0"),
        lambda q: q.fill("#in-moisture", "60"), lambda q: q.click("label:has(input[value=sandy_loam])"),
        lambda q: q.click("button[type=submit]"),
    ])
    run_task("Assess okra with only rough knowledge (preset plus three rough levels)", [
        lambda q: q.click("label:has(input[value=okra])"),
        lambda q: (q.select_option("#state", "Oyo"), q.wait_for_timeout(300)),
        lambda q: q.select_option("select[data-rough=ph]", "moderately_acidic"),
        lambda q: q.select_option("select[data-rough=organic_carbon]", "low"),
        lambda q: q.select_option("select[data-rough=moisture]", "moist"),
        lambda q: q.click("button[type=submit]"),
    ])
    M["tasks"] = tasks

    # U2. Keyboard-only completion and visible focus
    t = b.new_context(viewport={"width": 1440, "height": 900}); route_fonts(t); q = t.new_page()
    q.goto(BASE + "/analyse?zone=guinea"); settle(q, 600)
    seen = []; focus_visible = []
    for i in range(80):
        q.keyboard.press("Tab")
        info = q.evaluate("""() => { const e=document.activeElement; const cs=getComputedStyle(e);
            const nxt = e.nextElementSibling; const ncs = nxt ? getComputedStyle(nxt) : null;
            return {tag:e.tagName, type:e.type||'', name:e.name||'', id:e.id||'', text:(e.innerText||'').slice(0,30),
                    outline: cs.outlineStyle!=='none' && parseFloat(cs.outlineWidth)>0,
                    sibOutline: ncs ? (ncs.outlineStyle!=='none' && parseFloat(ncs.outlineWidth)>0) : false}; }""")
        seen.append(info); focus_visible.append(info["outline"] or info["sibOutline"])
        if info["tag"] == "BUTTON" and info["type"] == "submit":
            break
    M["keyboard"] = {"tab_stops_to_submit": len(seen), "reached_submit": seen[-1]["tag"] == "BUTTON",
                     "focus_visible_pct": round(100 * sum(focus_visible) / len(focus_visible), 1)}
    q.keyboard.press("Enter"); q.wait_for_url("**/result/**", timeout=8000)
    M["keyboard"]["submitted_with_enter"] = "/result/" in q.url
    t.close()

    # U3. Accessible names for every form control
    t = b.new_context(viewport={"width": 1440, "height": 900}); q = t.new_page()
    q.goto(BASE + "/analyse"); settle(q, 400)
    M["labels"] = q.evaluate("""() => { const els=[...document.querySelectorAll('input,select,textarea,button')];
        const named = els.filter(e => e.getAttribute('aria-label') || (e.id && document.querySelector('label[for="'+e.id+'"]')) || e.closest('label') || (e.tagName==='BUTTON' && e.innerText.trim()));
        return {controls: els.length, named: named.length, unnamed: els.filter(e=>!named.includes(e)).map(e=>e.outerHTML.slice(0,80))}; }""")
    t.close()

    # U4. Responsive: no horizontal overflow at the four reference widths on every page
    resp = []
    for w in (375, 768, 1024, 1440):
        t = b.new_context(viewport={"width": w, "height": 900}); route_fonts(t); q = t.new_page()
        for path in ("/", "/analyse?zone=forest", kadawa_url.replace(BASE, ""), "/method", "/knowledge"):
            q.goto(BASE + path); settle(q, 500)
            ov = q.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            resp.append({"width": w, "page": path.split("?")[0] if not path.startswith("/result") else "/result", "overflow_px": ov})
        t.close()
    M["responsive"] = resp

    # U5. Page load timing (local)
    loads = []
    t = b.new_context(viewport={"width": 1440, "height": 900}); route_fonts(t); q = t.new_page()
    for path in ("/", "/analyse", kadawa_url.replace(BASE, ""), "/method", "/knowledge"):
        vals = []
        for _ in range(5):
            q.goto(BASE + path); q.wait_for_load_state("load")
            vals.append(q.evaluate("(() => { const n=performance.getEntriesByType('navigation')[0]; return {dcl:n.domContentLoadedEventEnd, load:n.loadEventEnd, bytes:n.transferSize}; })()"))
        loads.append({"page": "/result" if path.startswith("/result") else path, "dcl_ms": round(statistics.median(v["dcl"] for v in vals), 1),
                      "load_ms": round(statistics.median(v["load"] for v in vals), 1), "html_bytes": vals[-1]["bytes"]})
    M["page_load"] = loads
    t.close()

    # U6. Reduced motion honoured
    t = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce"); q = t.new_page()
    q.goto(BASE + "/"); q.wait_for_load_state("load"); q.wait_for_timeout(200)
    M["reduced_motion_hero_visible"] = q.evaluate("getComputedStyle(document.querySelector('.reveal')).opacity") == "1"
    t.close()
    M["page_errors"] = errors
    b.close()

# ---------------------------------------------------------------- API latency over HTTP (gunicorn, 2 workers x 4 threads)
body = json.dumps({"crop": "tomato", "ph": 5.6, "nitrogen": 1.2, "phosphorus": 10, "potassium": 0.2, "organic_carbon": 0.9, "ec": 1.0, "moisture": 65, "texture": "loam"}).encode()
lat = []
for i in range(220):
    req = urllib.request.Request(BASE + "/api/preview", data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); urllib.request.urlopen(req).read(); dt = (time.perf_counter() - t0) * 1000
    if i >= 20: lat.append(dt)
lat.sort()
M["api_latency_ms"] = {"n": len(lat), "median": round(statistics.median(lat), 1), "p95": round(lat[int(.95 * len(lat)) - 1], 1), "max": round(lat[-1], 1)}

# concurrency: 50 parallel clients x 10 requests
import concurrent.futures as cf
def burst(_):
    out = []
    for _ in range(10):
        req = urllib.request.Request(BASE + "/api/preview", data=body, headers={"Content-Type": "application/json"})
        t0 = time.perf_counter(); r = urllib.request.urlopen(req); r.read(); out.append(((time.perf_counter() - t0) * 1000, r.status))
    return out
t0 = time.perf_counter()
with cf.ThreadPoolExecutor(50) as ex:
    res = [x for chunk in ex.map(burst, range(50)) for x in chunk]
wall = time.perf_counter() - t0
ms = sorted(x[0] for x in res)
M["load_test"] = {"clients": 50, "requests": len(res), "ok": sum(1 for x in res if x[1] == 200), "wall_s": round(wall, 2),
                  "throughput_rps": round(len(res) / wall, 1), "median_ms": round(statistics.median(ms), 1), "p95_ms": round(ms[int(.95 * len(ms)) - 1], 1)}

json.dump(M, open(os.path.join(OUTD, "ui_metrics.json"), "w"), indent=1)
print(json.dumps(M, indent=1)[:4000])
