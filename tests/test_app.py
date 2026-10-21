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
