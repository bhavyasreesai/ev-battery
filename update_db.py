import sqlite3

conn = sqlite3.connect("data/battery_passport.db")
cursor = conn.cursor()

cursor.execute("""
UPDATE battery_listings
SET seller_city = 'Potheri',
    seller_state = 'Tamil Nadu'
WHERE listing_id = 2
""")

conn.commit()
conn.close()

print("Listing 2 updated!")
