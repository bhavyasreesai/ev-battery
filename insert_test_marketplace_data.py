import sqlite3
from datetime import datetime

DB_PATH = "data/battery_passport.db"

batteries = [
    ("TEST-MKT-001", "LFP", 45, 300, "Test Motors", "Test Seller 1", "Chennai"),
    ("TEST-MKT-002", "NMC", 60, 350, "Test Motors", "Test Seller 2", "Bengaluru"),
    ("TEST-MKT-003", "NCA", 75, 400, "Test Motors", "Test Seller 3", "Hyderabad"),
    ("TEST-MKT-004", "LFP", 50, 320, "Test Motors", "Test Seller 4", "Mumbai"),
    ("TEST-MKT-005", "NMC", 40, 280, "Test Motors", "Test Seller 5", "Pune"),
    ("TEST-MKT-006", "LFP", 35, 250, "Test Motors", "Test Seller 6", "Delhi"),
    ("TEST-MKT-007", "NCA", 70, 390, "Test Motors", "Test Seller 7", "Kolkata"),
    ("TEST-MKT-008", "NMC", 55, 330, "Test Motors", "Test Seller 8", "Ahmedabad"),
    ("TEST-MKT-009", "LFP", 30, 220, "Test Motors", "Test Seller 9", "Jaipur"),
    ("TEST-MKT-010", "NMC", 65, 360, "Test Motors", "Test Seller 10", "Kochi"),
    ("TEST-MKT-011", "LFP", 48, 310, "Test Motors", "Test Seller 11", "Coimbatore"),
    ("TEST-MKT-012", "NCA", 72, 410, "Test Motors", "Test Seller 12", "Vijayawada"),
]

locations = {
    "Chennai": ("Tamil Nadu", "600001"),
    "Bengaluru": ("Karnataka", "560001"),
    "Hyderabad": ("Telangana", "500001"),
    "Mumbai": ("Maharashtra", "400001"),
    "Pune": ("Maharashtra", "411001"),
    "Delhi": ("Delhi", "110001"),
    "Kolkata": ("West Bengal", "700001"),
    "Ahmedabad": ("Gujarat", "380001"),
    "Jaipur": ("Rajasthan", "302001"),
    "Kochi": ("Kerala", "682001"),
    "Coimbatore": ("Tamil Nadu", "641001"),
    "Vijayawada": ("Andhra Pradesh", "520001"),
}

asking_prices = [
    42000, 55000, 68000, 47000, 38000, 32000,
    62000, 50000, 28000, 58000, 43000, 65000
]

selling_prices = [
    38000, 50000, 61000, 42000, 34000, 29000,
    57000, 45000, 25000
]

# Each entry: seller battery number, buyer city, buyer name
buyers = [
    (1, "Bengaluru", "Test Buyer 1"),
    (2, "Chennai", "Test Buyer 2"),
    (3, "Mumbai", "Test Buyer 3"),
    (4, "Pune", "Test Buyer 4"),
    (5, "Delhi", "Test Buyer 5"),
    (6, "Hyderabad", "Test Buyer 6"),
    (7, "Kochi", "Test Buyer 7"),
    (8, "Jaipur", "Test Buyer 8"),
    (9, "Coimbatore", "Test Buyer 9"),
]

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

try:
    for i, battery in enumerate(batteries):
        battery_id, chemistry, capacity, weight, manufacturer, seller, city = battery
        cursor.execute("""
            INSERT OR IGNORE INTO batteries
            (battery_id, chemistry, capacity_kwh, weight_kg,
             manufacturer, current_owner, current_location, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            battery_id, chemistry, capacity, weight,
            manufacturer, seller, city, datetime.now().isoformat()
        ))

        state, pincode = locations[city]

        cursor.execute("""
            SELECT listing_id FROM battery_listings
            WHERE battery_id = ? AND seller_name = ?
        """, (battery_id, seller))

        listing = cursor.fetchone()

        if listing is None:
            status = "Sold" if i < 9 else "Available"
            cursor.execute("""
                INSERT INTO battery_listings
                (battery_id, seller_name, seller_city, seller_state,
                 seller_pincode, asking_price, status, listed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                battery_id, seller, city, state, pincode,
                asking_prices[i], status, datetime.now().isoformat()
            ))
            listing_id = cursor.lastrowid
        else:
            listing_id = listing[0]

        if i < 9:
            buyer_number, buyer_city, buyer_name = buyers[i]
            buyer_state, buyer_pincode = locations[buyer_city]

            cursor.execute("""
                SELECT transaction_id FROM transactions
                WHERE listing_id = ?
            """, (listing_id,))

            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO transactions
                    (listing_id, battery_id, seller_name, buyer_name,
                     buyer_city, buyer_state, buyer_pincode,
                     selling_price, transaction_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    listing_id, battery_id, seller, buyer_name,
                    buyer_city, buyer_state, buyer_pincode,
                    selling_prices[i], datetime.now().isoformat(),
                    "Completed"
                ))

    conn.commit()

    for table in ["batteries", "battery_listings", "transactions"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cursor.fetchone()[0]} total records")

    print("\nIllustrative marketplace test data inserted successfully.")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
