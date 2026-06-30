import sqlite3
import json

conn = sqlite3.connect("backend/energy_forecast.db")
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, name, display_name, is_active, status FROM model_registry")
    rows = cursor.fetchall()
    print("Database Model Registry Rows:")
    for row in rows:
        print(row)
except Exception as e:
    print("Error querying database:", e)
finally:
    conn.close()
