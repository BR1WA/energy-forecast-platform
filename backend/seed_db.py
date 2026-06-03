"""
Seed database with historical forecasts to populate charts for the presentation.
"""
import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
import random
import json

from app.database import SessionLocal
from app.models import User, Forecast, Alert
from app.services.forecast_service import get_forecast_service
from app.services.auth_service import hash_password

def seed_database():
    db = SessionLocal()
    try:
        # Get or create admin user
        admin = db.query(User).filter(User.email == "admin@energyforecast.com").first()
        if not admin:
            admin = User(
                email="admin@energyforecast.com",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()

        service = get_forecast_service()
        if not service.samples:
            print("No samples found. Cannot generate realistic forecasts.")
            return

        sample_name = list(service.samples.keys())[0]
        sample_data = service.samples[sample_name]
        
        models = list(service.models.keys())
        if not models:
            print("No models loaded.")
            return

        print(f"Seeding with {len(models)} models using sample '{sample_name}'...")

        # Generate 20 forecasts over the past 7 days
        now = datetime.now(timezone.utc)
        
        for i in range(20):
            # Random time in the last 7 days
            days_ago = random.uniform(0, 7)
            created_at = now - timedelta(days=days_ago)
            
            # Random model
            model_name = random.choice(models)
            
            # Run prediction
            targets = sample_data['targets']
            calendar = sample_data['calendar']
            
            # Add some random noise to make them look different
            noise = np.random.normal(0, 0.05, targets.shape)
            noisy_targets = targets * (1 + noise)
            
            preds, alerts = service.predict(model_name, noisy_targets, calendar)
            
            # Create forecast
            forecast = Forecast(
                user_id=admin.id,
                model_name=model_name,
                input_start=created_at - timedelta(hours=120),
                input_end=created_at - timedelta(hours=24),
                predictions=preds.tolist(),
                metrics={"accuracy": round(random.uniform(92.0, 98.5), 2)},
                created_at=created_at
            )
            db.add(forecast)
            db.flush() # Get forecast ID
            
            # Create alerts
            for alert_data in alerts:
                alert = Alert(
                    user_id=admin.id,
                    forecast_id=forecast.id,
                    alert_type=alert_data['alert_type'],
                    severity=alert_data['severity'],
                    message=alert_data['message'],
                    peak_kw=alert_data['peak_kw'],
                    is_acknowledged=random.choice([True, False]),
                    created_at=created_at
                )
                db.add(alert)
                
        db.commit()
        print("Successfully seeded 20 historical forecasts and alerts!")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import numpy as np
    seed_database()
