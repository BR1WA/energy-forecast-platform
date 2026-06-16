import sqlite3

def upgrade_db():
    try:
        conn = sqlite3.connect("energy_forecast.db")
        cursor = conn.cursor()
        print("Adding is_setup_complete column...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_setup_complete BOOLEAN DEFAULT 0 NOT NULL;")
        print("is_setup_complete added.")
    except Exception as e:
        print("Error adding is_setup_complete:", e)

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN preferences JSON;")
        print("preferences added.")
    except Exception as e:
        print("Error adding preferences:", e)

    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    upgrade_db()
