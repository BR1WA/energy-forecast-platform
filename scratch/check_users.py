import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.append(r"c:\Users\salah\Documents\MASTER\PFE2\backend")

from app.database import SessionLocal
from app.models import User

db = SessionLocal()
try:
    users = db.query(User).all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Name: {u.full_name}, Avatar: {u.avatar_url}")
finally:
    db.close()
