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
from app.migrations import run_migrations
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

    try:
        logger.info("[DB] Running database migrations...")
        run_migrations()
        logger.info("[DB] Database migrations completed successfully.")
    except Exception:
        logger.exception("[DB] Database migration failed; refusing to start.")
        raise

    # Initialise the forecast service singleton (lazy — no model is loaded until a request comes in)
    get_forecast_service()
    logger.info("[ML] ForecastService singleton initialised (model will be loaded on first request).")

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

    async def simulation_loop():
        logger.info("[SIMULATION-LOOP] Starting background simulation loop...")
        from app.services.simulation_service import simulation_service
        from app.database import SessionLocal
        from app.models import SmartMeterReading
        from datetime import datetime, timezone
        import random
        import math
        import time

        while True:
            try:
                if simulation_service.is_running:
                    db = SessionLocal()
                    try:
                        # Base load by day part
                        base_map = {
                            "morning": 0.8,
                            "afternoon": 0.4,
                            "evening": 1.8,
                            "night": 0.2
                        }
                        gap = base_map.get(simulation_service.day_part, 0.5)
                        
                        # Add occupants effect
                        gap += simulation_service.occupants * 0.15
                        
                        # Add Air Conditioner effect (scaled by temperature)
                        ac_map = {
                            "off": 0.0,
                            "low": 0.4,
                            "medium": 0.9,
                            "high": 1.8
                        }
                        ac_base = ac_map.get(simulation_service.ac_level, 0.0)
                        if simulation_service.temperature > 30.0:
                            ac_base *= 1.25
                        gap += ac_base
                        
                        # Add Washing Machine effect
                        if simulation_service.washing_machine:
                            gap += 0.8
                            
                        # Add Solar Panels offset (only during daylight)
                        solar_map = {
                            "off": 0.0,
                            "low": -0.4,
                            "high": -1.2
                        }
                        if simulation_service.day_part in ("morning", "afternoon"):
                            gap += solar_map.get(simulation_service.solar, 0.0)
                            
                        # Add slight noise and clamp positive
                        gap += random.uniform(-0.08, 0.08)
                        gap = max(0.02, gap)

                        # sub-metering breakdown (in Wh)
                        # sub_metering_1: Kitchen (washing machine / appliances)
                        sub1 = 800.0 if simulation_service.washing_machine else 50.0
                        sub1 += random.uniform(-10.0, 10.0)
                        sub1 = max(0.0, sub1)
                        
                        # sub_metering_3: HVAC (AC)
                        sub3 = ac_base * 1000.0
                        sub3 += random.uniform(-20.0, 20.0)
                        sub3 = max(0.0, sub3)
                        
                        # sub_metering_2: Laundry/Other
                        sub2 = gap * 150.0 + random.uniform(-15.0, 15.0)
                        sub2 = max(0.0, sub2)

                        grp = gap * 0.08 + random.uniform(-0.01, 0.01)
                        voltage = 230.0 + random.uniform(-1.0, 1.0)
                        intensity = (gap * 1000.0) / voltage

                        db_reading = SmartMeterReading(
                            gap=round(gap, 3),
                            grp=round(grp, 3),
                            voltage=round(voltage, 1),
                            intensity=round(intensity, 2),
                            sub_metering_1=round(sub1, 2),
                            sub_metering_2=round(sub2, 2),
                            sub_metering_3=round(sub3, 2),
                            timestamp=datetime.now(timezone.utc)
                        )
                        db.add(db_reading)
                        db.commit()
                        logger.info(f"[SIMULATION-LOOP] Inserted simulated smart meter reading: {gap:.3f} kW")
                    except Exception as db_err:
                        logger.error(f"[SIMULATION-LOOP] Database write error: {db_err}")
                        db.rollback()
                    finally:
                        db.close()
            except Exception as e:
                logger.error(f"[SIMULATION-LOOP] Loop exception: {e}")
            await asyncio.sleep(5)

    loop_task = asyncio.create_task(auto_forecast_loop())
    sim_task = asyncio.create_task(simulation_loop())

    logger.info("[APP] Server ready!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("[APP] Shutting down...")
    loop_task.cancel()
    sim_task.cancel()



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
    """Process liveness alias; dependency readiness lives under /api/v1/system/ready."""
    return {
        "status": "alive",
        "readiness": "/api/v1/system/ready",
    }
