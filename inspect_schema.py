import sqlite3

conn = sqlite3.connect("data/battery_passport.db")
cursor = conn.cursor()

for table in ["batteries", "battery_listings", "transactions", "ownership"]:
    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """, (table,))
    print("\n", table)
    print(cursor.fetchone()[0])

conn.close()
