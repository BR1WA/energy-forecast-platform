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
from app.database import engine, Base, SessionLocal
from app.routers import (
    auth, forecast, alerts, analytics, admin, settings as settings_router,
    multi_site, system, dashboard, data_mode, consumption,
    simulation, models_registry, ingestion, recommendations
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
    forecast_service = get_forecast_service()
    with SessionLocal() as db:
        forecast_service.sync_registry(db)
    logger.info("[ML] ForecastService singleton initialised (model will be loaded on first request).")

    # Start only explicitly user-controlled simulator sessions. Alerts are
    # evaluated from persisted meter data in a later worker phase.
    import asyncio

    async def simulation_loop():
        logger.info("[SIMULATION-LOOP] Starting background simulation loop...")
        from app.services.simulation_service import simulation_service
        from app.database import SessionLocal
        from app.models import Meter, SimulationSession
        from app.schemas import MeterSample
        from app.services.ingestion_service import ingestion_service

        while True:
            try:
                db = SessionLocal()
                try:
                    sessions = db.query(SimulationSession).filter(SimulationSession.is_running.is_(True)).all()
                    for session in sessions:
                        meter = db.query(Meter).filter(Meter.site_id == session.site_id).order_by(Meter.id).first()
                        if meter is None:
                            continue
                        ingestion_service.ingest(
                            db,
                            meter,
                            [MeterSample.model_validate(simulation_service.reading_for_configuration(session.configuration or {}))],
                            source="simulation",
                        )
                    if sessions:
                        db.commit()
                except Exception as db_err:
                    logger.error(f"[SIMULATION-LOOP] Database write error: {db_err}")
                    db.rollback()
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"[SIMULATION-LOOP] Loop exception: {e}")
            await asyncio.sleep(5)

    sim_task = asyncio.create_task(simulation_loop())

    logger.info("[APP] Server ready!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("[APP] Shutting down...")
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

# CORS: only the configured deployed frontend is trusted outside local development.
cors_origins = [settings.FRONTEND_URL]
if settings.DEBUG:
    cors_origins.extend(["http://localhost:3000", "http://localhost:3001"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(cors_origins)),
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
app.include_router(system.router)
app.include_router(dashboard.router)
app.include_router(data_mode.router)
app.include_router(consumption.router)
app.include_router(simulation.router)
app.include_router(ingestion.router)
app.include_router(models_registry.router)
app.include_router(recommendations.router)


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
