"""
EnergyForecast API — Main FastAPI Application
Master's PFE: Residential Energy Consumption Forecasting Platform
"""
import time
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import engine, Base
from app.routers import (
    auth, forecast, alerts, analytics, admin, settings as settings_router,
    multi_site, billing, system, dashboard, data_mode, consumption,
    simulation, models_registry
)
from app.services.forecast_service import get_forecast_service
from app.limiter import limiter
from app.logging_config import configure_logging, RequestIDMiddleware

# Configure logging at startup
configure_logging()
logger = logging.getLogger("app.main")

settings = get_settings()

# Ensure static directories exist before FastAPI is configured
os.makedirs("static/avatars", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)

    # Ensure static/avatars directory exists
    os.makedirs("static/avatars", exist_ok=True)

    # Create database tables via migrations
    # Programmatic Database Migrations via Alembic
    from alembic.config import Config
    from alembic import command

    try:
        logger.info("[DB] Running database migrations...")
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(alembic_cfg, "head")
        logger.info("[DB] Database migrations completed successfully.")
    except Exception as e:
        logger.warning(f"[DB] Migration warning on startup (can be ignored if database is already at head): {e}")

    # Pre-load ML models
    service = get_forecast_service()
    logger.info(f"[ML] Models ready: {list(service.models.keys())}")

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
            logger.info(f"[DB] Default admin user created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()

    # Start auto-forecasting and alert check ticker task
    import asyncio
    from app.services.websocket_manager import manager

    async def auto_forecast_loop():
        logger.info("[AUTO-FORECAST] Starting background loop...")
        await asyncio.sleep(5)  # Wait for startup to complete fully
        while True:
            try:
                import random
                from datetime import datetime, timezone
                if manager.active_connections:
                    val = round(random.uniform(2.5, 5.2), 2)
                    logger.info(f"[AUTO-FORECAST] Simulating load check: current usage {val} kW")
                    
                    from app.database import SessionLocal
                    from app.models import Alert, AlertConfig
                    db_session = SessionLocal()
                    try:
                        for user_id_str in list(manager.active_connections.keys()):
                            try:
                                uid = int(user_id_str)
                                # Query AlertConfig for this user
                                config = db_session.query(AlertConfig).filter(AlertConfig.user_id == uid).first()
                                threshold = config.threshold_kw if config else 3.0
                                
                                # Peak Consumption Alert
                                if val > threshold:
                                    alert_payload = {
                                        "type": "alert",
                                        "severity": "high",
                                        "title": "Peak Consumption Warning",
                                        "message": f"Real-time usage is {val} kW, exceeding safety threshold of {threshold} kW. Recommend shifting load.",
                                        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                    }
                                    
                                    db_alert = Alert(
                                        user_id=uid,
                                        alert_type="peak_demand",
                                        message=alert_payload["message"],
                                        severity=alert_payload["severity"],
                                        is_acknowledged=False
                                    )
                                    db_session.add(db_alert)
                                    db_session.commit()
                                    db_session.refresh(db_alert)
                                    
                                    personal_payload = alert_payload.copy()
                                    personal_payload["id"] = str(db_alert.id)
                                    
                                    logger.info(f"[AUTO-FORECAST] Broadcasting alert to user {uid}: {personal_payload['message']} (threshold {threshold} kW)")
                                    await manager.broadcast_to_client(user_id_str, personal_payload)
                                    
                                # Budget Warning Alert
                                from app.models.models import EnergyBudget
                                from datetime import timedelta
                                budget = db_session.query(EnergyBudget).filter(EnergyBudget.user_id == uid).first()
                                if budget and budget.monthly_budget_mad > 0:
                                    # Simulate projected cost based on current behavior
                                    projected_cost = budget.monthly_budget_mad * random.uniform(0.85, 1.1)
                                    if projected_cost >= (budget.monthly_budget_mad * 0.9):
                                        # Check for debounce (24 hours)
                                        recent_budget_alert = db_session.query(Alert).filter(
                                            Alert.user_id == uid,
                                            Alert.alert_type == "budget_warning",
                                            Alert.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
                                        ).first()
                                        
                                        if not recent_budget_alert:
                                            budget_payload = {
                                                "type": "alert",
                                                "severity": "high",
                                                "title": "Budget Warning",
                                                "message": f"Projected monthly cost ({projected_cost:.2f} MAD) is exceeding 90% of your budget ({budget.monthly_budget_mad:.2f} MAD).",
                                                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                            }
                                            
                                            db_budget_alert = Alert(
                                                user_id=uid,
                                                alert_type="budget_warning",
                                                message=budget_payload["message"],
                                                severity=budget_payload["severity"],
                                                is_acknowledged=False
                                            )
                                            db_session.add(db_budget_alert)
                                            db_session.commit()
                                            db_session.refresh(db_budget_alert)
                                            
                                            personal_budget_payload = budget_payload.copy()
                                            personal_budget_payload["id"] = str(db_budget_alert.id)
                                            
                                            logger.info(f"[AUTO-FORECAST] Broadcasting budget warning to user {uid}")
                                            await manager.broadcast_to_client(user_id_str, personal_budget_payload)
                            except Exception as inner_err:
                                logger.error(f"[AUTO-FORECAST] Failed to save/send alert to user {user_id_str}: {inner_err}")
                                db_session.rollback()
                    except Exception as db_err:
                        logger.error(f"[AUTO-FORECAST] DB query/log error: {db_err}")
                    finally:
                        db_session.close()
            except Exception as e:
                logger.error(f"[AUTO-FORECAST] Loop exception: {e}")
            await asyncio.sleep(30)

    loop_task = asyncio.create_task(auto_forecast_loop())

    logger.info("[APP] Server ready!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("[APP] Shutting down...")
    loop_task.cancel()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Energy Forecasting Platform — "
        "3 ML models (PatchTST, SOTA Hybrid, CNN-BiLSTM), "
        "JWT authentication, RBAC, and alert management."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Register RequestIDMiddleware early in middleware stack
app.add_middleware(RequestIDMiddleware)

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
app.include_router(settings_router.router)
app.include_router(multi_site.router)
app.include_router(billing.router)
app.include_router(system.router)
app.include_router(dashboard.router)
app.include_router(data_mode.router)
app.include_router(consumption.router)
app.include_router(simulation.router)
app.include_router(models_registry.router)


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
