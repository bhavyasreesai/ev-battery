
"""Battery Passport and EV Battery Marketplace database."""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data") / "battery_passport.db"


SCHEMA = """
         CREATE TABLE IF NOT EXISTS batteries (
                                                  battery_id TEXT PRIMARY KEY,
                                                  chemistry TEXT NOT NULL,
                                                  capacity_kwh REAL,
                                                  weight_kg REAL,
                                                  manufacturer TEXT,
                                                  manufacture_date TEXT,
                                                  current_owner TEXT,
                                                  current_location TEXT,
                                                  created_at TEXT
         );

         CREATE TABLE IF NOT EXISTS ownership (
                                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                  battery_id TEXT NOT NULL,
                                                  owner TEXT NOT NULL,
                                                  role TEXT,
                                                  from_date TEXT,
                                                  to_date TEXT,
                                                  FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             );

         CREATE TABLE IF NOT EXISTS health_snapshots (
                                                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                         battery_id TEXT NOT NULL,
                                                         timestamp TEXT,
                                                         cycle_count INTEGER,
                                                         soh REAL,
                                                         rul INTEGER,
                                                         voltage REAL,
                                                         temperature REAL,
                                                         FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             );

         CREATE TABLE IF NOT EXISTS decisions (
                                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                  battery_id TEXT NOT NULL,
                                                  timestamp TEXT,
                                                  action TEXT,
                                                  confidence REAL,
                                                  reasons TEXT,
                                                  recommended_centre TEXT,
                                                  FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             );

         CREATE TABLE IF NOT EXISTS material_recovery (
                                                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                          battery_id TEXT NOT NULL,
                                                          timestamp TEXT,
                                                          material TEXT,
                                                          recovered_kg REAL,
                                                          FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             );

         CREATE TABLE IF NOT EXISTS battery_listings (
                                                         listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                         battery_id TEXT NOT NULL,
                                                         seller_name TEXT NOT NULL,
                                                         seller_city TEXT NOT NULL,
                                                         seller_state TEXT NOT NULL,
                                                         seller_pincode TEXT NOT NULL,
                                                         asking_price REAL NOT NULL,
                                                         status TEXT NOT NULL DEFAULT 'Available',
                                                         listed_at TEXT NOT NULL,
                                                         FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             );

         CREATE TABLE IF NOT EXISTS transactions (
                                                     transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                     listing_id INTEGER NOT NULL,
                                                     battery_id TEXT NOT NULL,
                                                     seller_name TEXT NOT NULL,
                                                     buyer_name TEXT NOT NULL,
                                                     buyer_city TEXT NOT NULL,
                                                     buyer_state TEXT NOT NULL,
                                                     buyer_pincode TEXT NOT NULL,
                                                     selling_price REAL NOT NULL,
                                                     transaction_date TEXT NOT NULL,
                                                     status TEXT NOT NULL DEFAULT 'Completed',
                                                     FOREIGN KEY (listing_id) REFERENCES battery_listings(listing_id),
             FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
             ); \
         """


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


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
        exists = con.execute(
            "SELECT 1 FROM batteries WHERE battery_id = ?",
            (battery_id,)
        ).fetchone()

        if not exists:
            raise ValueError(f"Battery {battery_id} does not exist")

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


def create_listing(battery_id, seller_name, seller_city,
                   seller_state, seller_pincode, asking_price):

    if asking_price <= 0:
        raise ValueError("Asking price must be greater than zero")

    now = datetime.utcnow().isoformat()

    with connect() as con:
        battery = con.execute("""
                              SELECT current_owner FROM batteries
                              WHERE battery_id = ?
                              """, (battery_id,)).fetchone()

        if not battery:
            raise ValueError("Battery is not registered")

        if battery[0] != seller_name:
            raise ValueError("Seller must be the current battery owner")

        existing = con.execute("""
                               SELECT 1 FROM battery_listings
                               WHERE battery_id = ? AND status = 'Available'
                               """, (battery_id,)).fetchone()

        if existing:
            raise ValueError("This battery already has an active listing")

        cur = con.execute("""
                          INSERT INTO battery_listings
                          (battery_id, seller_name, seller_city, seller_state,
                           seller_pincode, asking_price, status, listed_at)
                          VALUES (?, ?, ?, ?, ?, ?, 'Available', ?)
                          """, (battery_id, seller_name, seller_city, seller_state,
                                seller_pincode, asking_price, now))

        return cur.lastrowid


def get_available_listings():
    with connect() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
                           SELECT l.*, b.chemistry, b.capacity_kwh,
                                  b.weight_kg, b.manufacturer
                           FROM battery_listings l
                                    JOIN batteries b ON l.battery_id = b.battery_id
                           WHERE l.status = 'Available'
                           ORDER BY l.listed_at DESC
                           """).fetchall()

        return [dict(row) for row in rows]


def complete_transaction(listing_id, buyer_name, buyer_city,
                         buyer_state, buyer_pincode, selling_price):

    if selling_price <= 0:
        raise ValueError("Selling price must be greater than zero")

    now = datetime.utcnow().isoformat()

    with connect() as con:
        listing = con.execute("""
                              SELECT battery_id, seller_name, asking_price
                              FROM battery_listings
                              WHERE listing_id = ? AND status = 'Available'
                              """, (listing_id,)).fetchone()

        if not listing:
            raise ValueError("Listing is unavailable or already sold")

        battery_id, seller_name, asking_price = listing

        if buyer_name == seller_name:
            raise ValueError("Seller cannot purchase their own listing")

        battery = con.execute("""
                              SELECT current_owner FROM batteries WHERE battery_id = ?
                              """, (battery_id,)).fetchone()

        if not battery or battery[0] != seller_name:
            raise ValueError("Seller is no longer the battery owner")

        con.execute("""
                    INSERT INTO transactions
                    (listing_id, battery_id, seller_name, buyer_name,
                     buyer_city, buyer_state, buyer_pincode,
                     selling_price, transaction_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completed')
                    """, (listing_id, battery_id, seller_name, buyer_name,
                          buyer_city, buyer_state, buyer_pincode,
                          selling_price, now))

        con.execute("""
                    UPDATE battery_listings
                    SET status = 'Sold'
                    WHERE listing_id = ?
                    """, (listing_id,))

        con.execute("""
                    UPDATE ownership SET to_date = ?
                    WHERE battery_id = ? AND to_date IS NULL
                    """, (now, battery_id))

        con.execute("""
                    INSERT INTO ownership
                        (battery_id, owner, role, from_date)
                    VALUES (?, ?, 'buyer', ?)
                    """, (battery_id, buyer_name, now))

        con.execute("""
                    UPDATE batteries
                    SET current_owner = ?, current_location = ?
                    WHERE battery_id = ?
                    """, (buyer_name, buyer_city, battery_id))

        return {
            "battery_id": battery_id,
            "seller": seller_name,
            "buyer": buyer_name,
            "asking_price": asking_price,
            "selling_price": selling_price
        }


def get_transactions():
    with connect() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
                           SELECT * FROM transactions
                           ORDER BY transaction_date DESC
                           """).fetchall()

        return [dict(row) for row in rows]


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
            "SELECT COUNT(*) AS c FROM batteries"
        ).fetchone()["c"]

        n_snapshots = con.execute(
            "SELECT COUNT(*) AS c FROM health_snapshots"
        ).fetchone()["c"]

        n_decisions = con.execute(
            "SELECT COUNT(*) AS c FROM decisions"
        ).fetchone()["c"]

        n_recovered = con.execute(
            "SELECT COUNT(*) AS c FROM material_recovery"
        ).fetchone()["c"]

        n_listings = con.execute(
            "SELECT COUNT(*) AS c FROM battery_listings"
        ).fetchone()["c"]

        n_transactions = con.execute(
            "SELECT COUNT(*) AS c FROM transactions"
        ).fetchone()["c"]

    return {
        "batteries": n_batteries,
        "health_snapshots": n_snapshots,
        "decisions": n_decisions,
        "material_records": n_recovered,
        "listings": n_listings,
        "transactions": n_transactions
    }


if __name__ == "__main__":
    init_db()
    print("Database tables are ready.")
    print("Summary:", get_summary())
