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
import numpy as np

from app.database import SessionLocal
from app.models import User, Forecast, Alert, ModelRegistry
from app.services.forecast_service import get_forecast_service
from app.services.auth_service import hash_password
from app.config import get_settings
from app.migrations import run_migrations

def seed_database():
    if os.getenv("ALLOW_DEMO_SEED", "").lower() != "true":
        raise SystemExit(
            "Demo seeding is disabled. Set ALLOW_DEMO_SEED=true explicitly."
        )

    settings = get_settings()
    if not settings.DEBUG:
        raise SystemExit("Demo seeding is allowed only when DEBUG=true.")

    demo_password = os.getenv("DEMO_USER_PASSWORD")
    if not demo_password or len(demo_password) < 12:
        raise SystemExit("Set DEMO_USER_PASSWORD to at least 12 characters.")

    run_migrations()
    db = SessionLocal()
    try:
        # Get or create admin user
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                role="admin",
                is_active=True,
                is_setup_complete=True,
                subscription_tier="pro",
            )
            db.add(admin)
            db.commit()

        # Seed additional users if they don't exist
        extra_users = [
            {"email": "operator@energyforecast.com", "full_name": "Jane Operator", "role": "analyst", "is_active": True},
            {"email": "viewer@energyforecast.com", "full_name": "Bob Viewer", "role": "viewer", "is_active": False},
            {"email": "alice@example.com", "full_name": "Alice Johnson", "role": "viewer", "is_active": False},
            {"email": "charlie@example.com", "full_name": "Charlie Brown", "role": "analyst", "is_active": True},
        ]
        for u_data in extra_users:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if not existing:
                new_user = User(
                    email=u_data["email"],
                    password_hash=hash_password(demo_password),
                    full_name=u_data["full_name"],
                    role=u_data["role"],
                    is_active=u_data["is_active"],
                )
                db.add(new_user)
        db.commit()

        service = get_forecast_service()
        if not service.samples:
            print("No samples found. Cannot generate realistic forecasts.")
            return

        sample_name = list(service.samples.keys())[0]
        sample_data = service.samples[sample_name]
        
        # Get model names from registry table
        service.get_available_models()
        models = [
            m.name
            for m in db.query(ModelRegistry).filter(ModelRegistry.horizon == 24).all()
        ]
        if not models:
            print("No models found in database ModelRegistry.")
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
            
            # Truncate to 96 steps for 24h models
            targets = sample_data['targets'][-96:]
            calendar = None
            
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
        import traceback
        traceback.print_exc()
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
