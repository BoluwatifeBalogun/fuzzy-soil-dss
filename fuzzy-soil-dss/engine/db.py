"""SQLite persistence: crop profiles, generated rule base, zones, query log, feedback."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from . import knowledge as K
from .fis import generate_rules

DB_PATH = os.environ.get("SOIL_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "soil.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS crop (
    crop_id TEXT PRIMARY KEY, name TEXT, scientific TEXT, profile_json TEXT
);
CREATE TABLE IF NOT EXISTS rule (
    rule_id TEXT PRIMARY KEY, crop_id TEXT, tier INTEGER, antecedent_json TEXT, not_json TEXT,
    consequent TEXT, weight REAL, source TEXT, text TEXT,
    FOREIGN KEY (crop_id) REFERENCES crop(crop_id)
);
CREATE TABLE IF NOT EXISTS zone (
    zone_id TEXT PRIMARY KEY, name TEXT, tagline TEXT, notes TEXT, preset_json TEXT, palette TEXT
);
CREATE TABLE IF NOT EXISTS state (
    name TEXT PRIMARY KEY, zone_id TEXT, FOREIGN KEY (zone_id) REFERENCES zone(zone_id)
);
CREATE TABLE IF NOT EXISTS query_log (
    query_id TEXT PRIMARY KEY, crop_id TEXT, state TEXT, inputs_json TEXT, result_json TEXT,
    score REAL, class TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT, query_id TEXT, helpful INTEGER, comment TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS ix_query_class ON query_log(class);
CREATE INDEX IF NOT EXISTS ix_query_crop ON query_log(crop_id);
CREATE INDEX IF NOT EXISTS ix_feedback_q ON feedback(query_id);
"""


def knowledge_hash():
    """Hash of the knowledge module source. When it changes, crops, rules and zones are reseeded."""
    path = os.path.join(os.path.dirname(__file__), "knowledge.py")
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(force=False):
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = connect()
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT value FROM meta WHERE key='knowledge_hash'").fetchone()
    h = knowledge_hash()
    if row is None or row["value"] != h:
        seed(conn)
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('knowledge_hash', ?)", (h,))
    conn.commit()
    conn.close()
    _RULE_CACHE.clear()


_RULE_CACHE = {}


def seed(conn):
    """(Re)write crops, rules, zones and states from knowledge.py. Query log and feedback are kept."""
    for key in K.CROP_ORDER:
        c = K.CROPS[key]
        conn.execute("INSERT OR REPLACE INTO crop VALUES (?,?,?,?)",
                     (key, c["name"], c["scientific"], json.dumps(c)))
        conn.execute("DELETE FROM rule WHERE crop_id=?", (key,))
        for r in generate_rules(key):
            extra = {k: r[k] for k in ("not", "any", "not_any") if r.get(k)}
            conn.execute("INSERT INTO rule VALUES (?,?,?,?,?,?,?,?,?)",
                         (r["rule_id"], key, r["tier"], json.dumps(r["antecedent"]),
                          json.dumps(extra) if extra else None,
                          r["consequent"], r["weight"], r["source"], r["text"]))
    for key in K.ZONE_ORDER:
        z = K.ZONES[key]
        conn.execute("INSERT OR REPLACE INTO zone VALUES (?,?,?,?,?,?)",
                     (key, z["name"], z["tagline"], z["notes"], json.dumps(z["preset"]), z["palette"]))
    for name, zone in K.STATES.items():
        conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (name, zone))


def load_rules(crop_id):
    if crop_id in _RULE_CACHE:
        return _RULE_CACHE[crop_id]
    conn = connect()
    rows = conn.execute("SELECT * FROM rule WHERE crop_id=? ORDER BY tier, rule_id", (crop_id,)).fetchall()
    conn.close()
    rules = []
    for r in rows:
        d = {
            "rule_id": r["rule_id"], "crop": r["crop_id"], "tier": r["tier"],
            "antecedent": json.loads(r["antecedent_json"]), "consequent": r["consequent"],
            "weight": r["weight"], "source": r["source"], "text": r["text"],
        }
        if r["not_json"]:
            d.update(json.loads(r["not_json"]))
        rules.append(d)
    _RULE_CACHE[crop_id] = rules
    return rules


def rule_counts():
    conn = connect()
    rows = conn.execute("SELECT crop_id, COUNT(*) AS n FROM rule GROUP BY crop_id").fetchall()
    conn.close()
    return {r["crop_id"]: r["n"] for r in rows}


def log_query(crop_id, state, inputs, result):
    qid = uuid.uuid4().hex[:12]
    state = (state or "")[:64]
    conn = connect()
    conn.execute("INSERT INTO query_log VALUES (?,?,?,?,?,?,?,?)",
                 (qid, crop_id, state, json.dumps(inputs), json.dumps(result), result["score"], result["class"],
                  datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    return qid


def get_query(qid):
    conn = connect()
    row = conn.execute("SELECT * FROM query_log WHERE query_id=?", (qid,)).fetchone()
    conn.close()
    if not row:
        return None
    return {"query_id": row["query_id"], "crop_id": row["crop_id"], "state": row["state"],
            "inputs": json.loads(row["inputs_json"]), "result": json.loads(row["result_json"]),
            "created_at": row["created_at"]}


def add_feedback(qid, helpful, comment):
    conn = connect()
    if not conn.execute("SELECT 1 FROM query_log WHERE query_id=?", (qid,)).fetchone():
        conn.close()
        return False
    conn.execute("INSERT INTO feedback (query_id, helpful, comment, created_at) VALUES (?,?,?,?)",
                 (qid, 1 if helpful else 0, comment, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    return True


def stats():
    conn = connect()
    n = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
    by_class = {r[0]: r[1] for r in conn.execute("SELECT class, COUNT(*) FROM query_log GROUP BY class")}
    by_crop = {r[0]: r[1] for r in conn.execute("SELECT crop_id, COUNT(*) FROM query_log GROUP BY crop_id")}
    rules = conn.execute("SELECT COUNT(*) FROM rule").fetchone()[0]
    conn.close()
    mfs = sum(len(K.FACTORS[f]["terms"]) for f in K.FACTOR_ORDER if f not in ("ph", "ec", "texture")) + len(K.CROP_ORDER) * (len(K.FACTORS["ph"]["terms"]) + len(K.FACTORS["ec"]["terms"]))
    return {"queries": n, "by_class": by_class, "by_crop": by_crop, "rules": rules, "mfs": mfs}
