"""
Module 6 - Battery Passport database (SQLite).

Stores:
  - battery identity (id, chemistry, capacity, manufacturer)
  - ownership chain (vendor -> buyer -> second owner -> recycler)
  - health snapshots (SoH, RUL, EOL over time)
  - recycling status (decision, centre, materials recovered)
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data") / "battery_passport.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS batteries (
    battery_id      TEXT PRIMARY KEY,
    chemistry       TEXT NOT NULL,
    capacity_kwh    REAL,
    weight_kg       REAL,
    manufacturer    TEXT,
    manufacture_date TEXT,
    current_owner   TEXT,
    current_location TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS ownership (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id      TEXT NOT NULL,
    owner           TEXT NOT NULL,
    role            TEXT,
    from_date       TEXT,
    to_date         TEXT,
    FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
);

CREATE TABLE IF NOT EXISTS health_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id      TEXT NOT NULL,
    timestamp       TEXT,
    cycle_count     INTEGER,
    soh             REAL,
    rul             INTEGER,
    voltage         REAL,
    temperature     REAL,
    FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id      TEXT NOT NULL,
    timestamp       TEXT,
    action          TEXT,
    confidence      REAL,
    reasons         TEXT,
    recommended_centre TEXT,
    FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
);

CREATE TABLE IF NOT EXISTS material_recovery (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id      TEXT NOT NULL,
    timestamp       TEXT,
    material        TEXT,
    recovered_kg    REAL,
    FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
);
"""


def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
    print(f"Initialised DB at {DB_PATH}")



def register_battery(battery_id, chemistry, capacity_kwh,
                     weight_kg, manufacturer, owner, location):
    now = datetime.utcnow().isoformat()

    with connect() as con:
        con.execute("""
            INSERT INTO batteries
            (battery_id, chemistry, capacity_kwh, weight_kg,
             manufacturer, current_owner, current_location, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (battery_id, chemistry, capacity_kwh, weight_kg,
              manufacturer, owner, location, now))

    print(f"Registered {battery_id}")



def transfer_ownership(battery_id, new_owner, role="buyer"):
    now = datetime.utcnow().isoformat()
    with connect() as con:
        con.execute("""
            UPDATE ownership SET to_date = ?
            WHERE battery_id = ? AND to_date IS NULL
        """, (now, battery_id))
        con.execute("""
            INSERT INTO ownership
            (battery_id, owner, role, from_date)
            VALUES (?, ?, ?, ?)
        """, (battery_id, new_owner, role, now))
        con.execute("""
            UPDATE batteries SET current_owner = ?
            WHERE battery_id = ?
        """, (new_owner, battery_id))
    print(f"{battery_id} transferred to {new_owner}")


def add_health_snapshot(battery_id, cycle_count, soh, rul,
                        voltage, temperature):
    with connect() as con:
        con.execute("""
            INSERT INTO health_snapshots
            (battery_id, timestamp, cycle_count, soh, rul,
             voltage, temperature)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (battery_id, datetime.utcnow().isoformat(),
              cycle_count, soh, rul, voltage, temperature))


def record_decision(battery_id, action, confidence, reasons,
                    recommended_centre=None):
    with connect() as con:
        con.execute("""
            INSERT INTO decisions
            (battery_id, timestamp, action, confidence, reasons,
             recommended_centre)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (battery_id, datetime.utcnow().isoformat(),
              action, confidence, " | ".join(reasons),
              recommended_centre))


def record_material(battery_id, material, recovered_kg):
    with connect() as con:
        con.execute("""
            INSERT INTO material_recovery
            (battery_id, timestamp, material, recovered_kg)
            VALUES (?, ?, ?, ?)
        """, (battery_id, datetime.utcnow().isoformat(),
              material, recovered_kg))


def get_battery(battery_id):
    with connect() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM batteries WHERE battery_id = ?",
            (battery_id,)
        ).fetchone()
        return dict(row) if row else None


def get_summary():
    with connect() as con:
        con.row_factory = sqlite3.Row
        n_batteries = con.execute(
            "SELECT COUNT(*) AS c FROM batteries").fetchone()["c"]
        n_snapshots = con.execute(
            "SELECT COUNT(*) AS c FROM health_snapshots").fetchone()["c"]
        n_decisions = con.execute(
            "SELECT COUNT(*) AS c FROM decisions").fetchone()["c"]
        n_recovered = con.execute(
            "SELECT COUNT(*) AS c FROM material_recovery").fetchone()["c"]
    return {
        "batteries": n_batteries,
        "health_snapshots": n_snapshots,
        "decisions": n_decisions,
        "material_records": n_recovered,
    }


if __name__ == "__main__":
    init_db()

    # Demo: register a few batteries
    register_battery("EVB-IN-000245", "LFP", 45.0, 320.0,
                     "Tata Motors", "Tata Dealer, Chennai", "Chennai")
    register_battery("EVB-IN-000246", "NMC", 60.0, 380.0,
                     "MG Motors", "MG Dealer, Delhi", "Delhi")
    register_battery("EVB-IN-000247", "NCA", 75.0, 420.0,
                     "Hyundai", "Hyundai Dealer, Pune", "Pune")

    # Ownership transfer
    transfer_ownership("EVB-IN-000245", "Ramesh Kumar", "buyer")

    # Health snapshots
    add_health_snapshot("EVB-IN-000245", 1420, 68.0, 420, 3.75, 28.0)
    add_health_snapshot("EVB-IN-000246",  950, 78.0, 780, 3.85, 30.0)
    add_health_snapshot("EVB-IN-000247",  510, 88.0, 1200, 3.90, 26.0)

    # Decision
    record_decision("EVB-IN-000245", "SECOND_LIFE", 0.85,
                    ["SoH 68% in second-life band", "RUL 420 cycles"],
                    recommended_centre="RC-002")

    # Material recovery
    record_material("EVB-IN-000245", "Li", 6.3)
    record_material("EVB-IN-000245", "Cu", 15.7)

    print()
    print("Summary:", get_summary())
    print("Battery EVB-IN-000245:", get_battery("EVB-IN-000245"))
