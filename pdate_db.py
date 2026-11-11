import sqlite3

conn = sqlite3.connect("data/battery_passport.db")
cursor = conn.cursor()

cursor.execute("""
               UPDATE battery_listings
               SET seller_city = 'Pune',
                   seller_state = 'Maharashtra'
               WHERE listing_id = 1
               """)

conn.commit()
conn.close()

print("Updated successfully!")