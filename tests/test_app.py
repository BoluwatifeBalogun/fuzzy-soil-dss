import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["SOIL_DB"] = "/tmp/test-soil.db"

import pytest  # noqa: E402


@pytest.fixture(scope="module")
def client():
    if os.path.exists("/tmp/test-soil.db"):
        os.remove("/tmp/test-soil.db")
    import importlib
    import engine.db as db
    importlib.reload(db)
    import app as appmod
    importlib.reload(appmod)
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as c:
        yield c


GOOD = {"crop": "tomato", "ph": 6.5, "nitrogen": 2.5, "phosphorus": 30, "potassium": 0.5, "organic_carbon": 2.0, "ec": 0.5, "moisture": 70, "texture": "loam"}


def test_pages_render(client):
    for path in ("/", "/analyse", "/analyse?zone=forest", "/method", "/knowledge?crop=onion", "/healthz"):
        assert client.get(path).status_code == 200, path


def test_form_round_trip_and_result_page(client):
    r = client.post("/evaluate", data={**GOOD, "state": "Kaduna"}, follow_redirects=False)
    assert r.status_code == 302
    page = client.get(r.headers["Location"])
    assert page.status_code == 200
    assert b"Highly suitable" in page.data or b"highly suitable" in page.data
    assert b"Adjust the values" in page.data


def test_form_validation_rerenders(client):
    r = client.post("/evaluate", data={**GOOD, "ph": "abc"})
    assert r.status_code == 400 and b"enter a number" in r.data


def test_api_evaluate_and_preview(client):
    r = client.post("/api/evaluate", json={**GOOD, "log": False})
    assert r.status_code == 200 and r.get_json()["class"] == "S1" and "query_id" not in r.get_json()
    r = client.post("/api/preview", json=GOOD)
    assert r.status_code == 200 and "memberships" in r.get_json()


@pytest.mark.parametrize("body", [[1, 2], "hello", 42, {"crop": ["tomato"]}, {**GOOD, "ph": True}, {**GOOD, "ph": float("nan")}, {**GOOD, "texture": "granite"}, {**GOOD, "ph": 99}])
def test_api_rejects_bad_payloads_without_500(client, body):
    r = client.post("/api/evaluate", json=body)
    assert r.status_code == 400 and "errors" in r.get_json()


def test_feedback_requires_existing_query(client):
    assert client.post("/feedback/nope", data={"helpful": "yes"}).status_code == 404


def test_result_404_is_a_page(client):
    r = client.get("/result/doesnotexist")
    assert r.status_code == 404 and b"does not exist" in r.data


def test_evaluation_is_fast(client):
    t0 = time.perf_counter()
    for _ in range(20):
        client.post("/api/preview", json=GOOD)
    assert (time.perf_counter() - t0) / 20 < 0.2  # well under the 2 s target in Section 3.18


def test_query_log_and_feedback_declare_foreign_keys(client):
    import sqlite3
    conn = sqlite3.connect("/tmp/test-soil.db")
    q = {r[2] for r in conn.execute("PRAGMA foreign_key_list(query_log)")}
    f = {r[2] for r in conn.execute("PRAGMA foreign_key_list(feedback)")}
    conn.close()
    assert q == {"crop"} and f == {"query_log"}


def test_feedback_on_a_real_query_is_stored(client):
    r = client.post("/api/evaluate", json={**GOOD, "log": True})
    qid = r.get_json()["query_id"]
    assert client.post(f"/feedback/{qid}", data={"helpful": "yes", "comment": "matches my plot"}).status_code == 302


def test_changing_the_knowledge_module_regenerates_rules(client):
    """Defect 8: a changed fingerprint makes init() rewrite the rule table; the query log is kept."""
    import sqlite3
    import engine.db as db
    conn = sqlite3.connect(db.DB_PATH)
    logged = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
    conn.execute("DELETE FROM rule WHERE crop_id='tomato'")
    conn.execute("UPDATE meta SET value='stale' WHERE key='knowledge_hash'")
    conn.commit(); conn.close()
    db.init()
    conn = sqlite3.connect(db.DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM rule WHERE crop_id='tomato'").fetchone()[0] > 0
    assert conn.execute("SELECT value FROM meta WHERE key='knowledge_hash'").fetchone()[0] == db.knowledge_hash()
    assert conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0] == logged
    conn.close()


def test_moderate_notes_are_worded_as_correctable(client):
    """Defect 13: an S2 note under a 'low' factor must not say 'moderate'."""
    worked = {"crop": "tomato", "ph": 5.6, "nitrogen": 1.2, "phosphorus": 10, "potassium": 0.2,
              "organic_carbon": 0.9, "ec": 1.0, "moisture": 65, "texture": "loam"}
    r = client.post("/evaluate", data=worked)
    page = client.get(r.headers["Location"]).data.decode()
    assert "correctable, not limiting" in page and "moderate, not limiting" not in page


def test_text_colours_meet_wcag_contrast():
    """Defect 10: body, secondary and hint text reach 4.5:1 on the light and dark backgrounds."""
    import re
    css = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "app.css")).read()
    tok = lambda name: re.search(r"--%s:\s*(#[0-9A-Fa-f]{6})" % name, css).group(1)
    def lum(h):
        r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    def ratio(a, b):
        la, lb = sorted([lum(a), lum(b)], reverse=True)
        return (la + 0.05) / (lb + 0.05)
    for fg in ("ink", "ink-2", "ink-3"):
        for bg in ("paper", "paper-2"):
            assert ratio(tok(fg), tok(bg)) >= 4.5, (fg, bg)
    dark_hint = re.search(r"--fg-3:\s*(#[0-9A-Fa-f]{6})", css.split(":root[data-theme=\"dark\"]")[1]).group(1)
    assert ratio(dark_hint, "#15100D") >= 4.5 and ratio(dark_hint, "#211A15") >= 4.5
