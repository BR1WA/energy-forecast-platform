import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.append(r"c:\Users\salah\Documents\MASTER\PFE2\backend")

from app.database import SessionLocal
from app.models import Forecast

db = SessionLocal()
try:
    forecasts = db.query(Forecast).order_by(Forecast.id.desc()).all()
    print(f"Total forecasts: {len(forecasts)}")
    for f in forecasts[:30]:
        print(f"ID: {f.id}, Model: {f.model_name}, Created At: {f.created_at}")
finally:
    db.close()
