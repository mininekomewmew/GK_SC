import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("predictions.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM predictions")
rows = cursor.fetchall()
print(f"Total rows in predictions.db: {len(rows)}")
for r in rows:
    print(r)
conn.close()
