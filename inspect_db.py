import sqlite3

conn = sqlite3.connect("data/battery_passport.db")
cursor = conn.cursor()

tables = ["batteries", "battery_listings", "transactions"]

for table in tables:
    print("\n==========", table, "==========")

    cursor.execute(f"SELECT * FROM {table}")

    columns = [description[0] for description in cursor.description]
    print(columns)

    for row in cursor.fetchall():
        print(row)

conn.close()