import sqlite3

conn = sqlite3.connect("data/battery_passport.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(ownership)")

print("Ownership table columns:")
for column in cursor.fetchall():
    print(column)

conn.close()
