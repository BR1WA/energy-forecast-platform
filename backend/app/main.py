"""
EnergyForecast API — Main FastAPI Application
Master's PFE: Residential Energy Consumption Forecasting Platform
"""
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, forecast, alerts, analytics, admin
from app.services.forecast_service import get_forecast_service
from app.limiter import limiter

settings = get_settings()

# Ensure static directories exist before FastAPI is configured
os.makedirs("static/avatars", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    print("=" * 60)
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)

    # Ensure static/avatars directory exists
    os.makedirs("static/avatars", exist_ok=True)

    # Create database tables via migrations
    # Programmatic Database Migrations via Alembic
    from alembic.config import Config
    from alembic import command

    try:
        print("[DB] Running database migrations...")
        Base.metadata.create_all(bind=engine)
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(alembic_cfg, "head")
        print("[DB] Database migrations completed successfully.")
    except Exception as e:
        print(f"[DB] Migration warning on startup (can be ignored if database is already at head): {e}")

    # Pre-load ML models
    service = get_forecast_service()
    print(f"[ML] Models ready: {list(service.models.keys())}")

    # Seed admin user if none exists
    from app.database import SessionLocal
    from app.models import User
    from app.services.auth_service import hash_password
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.role == "admin").first()
        if not admin_user:
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"[DB] Default admin user created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()

    # Start auto-forecasting and alert check ticker task
    import asyncio
    from app.services.websocket_manager import manager

    async def auto_forecast_loop():
        print("[AUTO-FORECAST] Starting background loop...")
        await asyncio.sleep(5)  # Wait for startup to complete fully
        while True:
            try:
                import random
                from datetime import datetime, timezone
                if manager.active_connections:
                    val = round(random.uniform(2.5, 5.2), 2)
                    threshold = 4.0
                    print(f"[AUTO-FORECAST] Simulating load check: current usage {val} kW (threshold {threshold} kW)")
                    
                    if val > threshold:
                        alert_payload = {
                            "type": "alert",
                            "severity": "high",
                            "title": "Peak Consumption Warning",
                            "message": f"Real-time usage is {val} kW, exceeding safety threshold of {threshold} kW. Recommend shifting load.",
                            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        }
                        
                        # Save alert to DB
                        from app.database import SessionLocal
                        from app.models import Alert, User
                        db_session = SessionLocal()
                        try:
                            first_user = db_session.query(User).first()
                            if first_user:
                                db_alert = Alert(
                                    user_id=first_user.id,
                                    title=alert_payload["title"],
                                    message=alert_payload["message"],
                                    severity=alert_payload["severity"],
                                    is_acknowledged=False
                                )
                                db_session.add(db_alert)
                                db_session.commit()
                                db_session.refresh(db_alert)
                                alert_payload["id"] = str(db_alert.id)
                        except Exception as db_err:
                            print(f"[AUTO-FORECAST] DB log error: {db_err}")
                        finally:
                            db_session.close()

                        print(f"[AUTO-FORECAST] Broadcasting alert: {alert_payload['message']}")
                        await manager.broadcast_global(alert_payload)
            except Exception as e:
                print(f"[AUTO-FORECAST] Loop exception: {e}")
            await asyncio.sleep(30)

    loop_task = asyncio.create_task(auto_forecast_loop())

    print("[APP] Server ready!")
    print("=" * 60)

    yield

    # Shutdown
    print("[APP] Shutting down...")
    loop_task.cancel()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Enterprise Energy Forecasting Platform — "
        "3 ML models (PatchTST, SOTA Hybrid, CNN-BiLSTM), "
        "JWT authentication, RBAC, and alert management."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (for avatars)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(forecast.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"])
def root():
    """API root — health check."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed health check endpoint."""
    service = get_forecast_service()
    return {
        "status": "healthy",
        "models_loaded": list(service.models.keys()),
        "models_count": len(service.models),
        "samples_loaded": len(service.samples),
    }
