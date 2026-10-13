"""
Analysis history logger.

Persists every battery analysis to a SQLite database so we have:
  - an audit trail (for regulatory compliance)
  - historical statistics
  - a way to look up any past decision

Database: data/history.db
Table:    analyses
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    battery_id        TEXT    NOT NULL,
    chemistry         TEXT,
    capacity_kwh      REAL,
    weight_kg         REAL,
    cycle             INTEGER,
    voltage           REAL,
    temperature       REAL,
    capacity          REAL,
    soh               REAL,
    rul               INTEGER,
    decision          TEXT,
    confidence        REAL,
    carbon_avoided_kg REAL,
    top_centre        TEXT,
    source            TEXT
);
CREATE INDEX IF NOT EXISTS idx_timestamp ON analyses(timestamp);
CREATE INDEX IF NOT EXISTS idx_battery   ON analyses(battery_id);
"""


def init_db() -> None:
    """Create the database and table if they don't exist."""
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)


def log_analysis(result: dict, source: str = "app") -> None:
    """
    Insert one analysis row into the history table.

    result: the dict returned by pipeline.analyse_battery()
    source: "app" (single) or "batch" (from batch page)
    """
    init_db()

    top_centre = "-"
    centres = result.get("centres") or []
    if centres:
        top_centre = centres[0].get("centre_name", "-")

    row = (
        datetime.now().isoformat(timespec="seconds"),
        str(result.get("battery_id", "-")),
        str(result.get("chemistry", "-")),
        float(result.get("capacity_kwh", 0) or 0),
        float(result.get("weight_kg", 0) or 0),
        int(result.get("cycle", 0) or 0),
        float(result.get("voltage", 0) or 0),
        float(result.get("temperature", 0) or 0),
        float(result.get("capacity", 0) or 0),
        float(result.get("soh", 0) or 0),
        int(result.get("rul", 0) or 0),
        str(result.get("decision", "-")),
        float(result.get("confidence", 0) or 0),
        float(result.get("carbon_avoided_kg", 0) or 0),
        top_centre,
        source,
    )

    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            INSERT INTO analyses
                (timestamp, battery_id, chemistry, capacity_kwh, weight_kg,
                 cycle, voltage, temperature, capacity, soh, rul, decision,
                 confidence, carbon_avoided_kg, top_centre, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )


def fetch_history(limit: Optional[int] = None) -> list:
    """
    Return all analyses as a list of dicts, newest first.
    If limit is None, returns everything.
    """
    init_db()
    sql = "SELECT * FROM analyses ORDER BY id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(sql).fetchall()]
    return rows


def count_rows() -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        return con.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]


def clear_history() -> None:
    """Delete all rows (useful during development)."""
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM analyses")


if __name__ == "__main__":
    # Self-test
    init_db()
    print(f"DB path: {DB_PATH}")
    print(f"Rows before: {count_rows()}")
    sample = {
        "battery_id": "TEST-001",
        "chemistry": "LFP",
        "capacity_kwh": 45, "weight_kg": 320,
        "cycle": 1000, "voltage": 3.8, "temperature": 28,
        "capacity": 30, "soh": 35,
        "rul": 0, "decision": "RECYCLE", "confidence": 0.9,
        "carbon_avoided_kg": 200,
        "centres": [{"centre_name": "Chennai LFP Recovery"}],
    }
    log_analysis(sample, source="test")
    print(f"Rows after:  {count_rows()}")
    latest = fetch_history(limit=1)
    print("Latest row:")
    for k, v in latest[0].items():
        print(f"  {k}: {v}")