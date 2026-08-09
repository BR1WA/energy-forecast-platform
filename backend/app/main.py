"""
EnergyForecast API — Main FastAPI Application
Master's PFE: Residential Energy Consumption Forecasting Platform
"""
import time
import os
import logging
import mimetypes
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
    system, consumption,
    simulation, ingestion, monitoring, recommendations, account
)
from app.migrations import run_migrations
from app.limiter import limiter
from app.logging_config import configure_logging, RequestIDMiddleware

# Configure logging at startup
configure_logging()
logger = logging.getLogger("app.main")

settings = get_settings()

# Debian slim images do not always load an OS MIME database. Register the
# normalized avatar format explicitly so the public avatar route is usable by
# browsers after a production restore as well as on developer machines.
mimetypes.add_type("image/webp", ".webp", strict=True)

# Ensure static directories exist before FastAPI is configured
os.makedirs(settings.AVATAR_STORAGE_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)

    # Ensure static/avatars directory exists
    os.makedirs(settings.AVATAR_STORAGE_DIR, exist_ok=True)

    try:
        logger.info("[DB] Running database migrations...")
        run_migrations()
        logger.info("[DB] Database migrations completed successfully.")
    except Exception:
        logger.exception("[DB] Database migration failed; refusing to start.")
        raise

    # Start only explicitly user-controlled simulator sessions. Alerts are
    # evaluated from persisted meter data in a later worker phase.
    import asyncio

    async def simulation_loop():
        logger.info("[SIMULATION-LOOP] Starting background simulation loop...")
        from app.services.simulation_service import simulation_service
        from app.database import SessionLocal
        from app.models import SimulationSession

        while True:
            try:
                db = SessionLocal()
                try:
                    sessions = db.query(SimulationSession).filter(SimulationSession.is_running.is_(True)).all()
                    for session in sessions:
                        simulation_service.advance_session(db, session)
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
        "one-site monitoring with truthful fixed 24-hour and gated 168-hour forecasts, "
        "with JWT authentication and alert management."
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

# Mount the configured durable avatar root before the broader static tree so a
# non-default local volume remains publicly addressable.
app.mount("/static/avatars", StaticFiles(directory=settings.AVATAR_STORAGE_DIR), name="avatars")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(forecast.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(settings_router.router)
app.include_router(system.router)
app.include_router(consumption.router)
app.include_router(simulation.router)
app.include_router(ingestion.router)
app.include_router(monitoring.router)
app.include_router(recommendations.router)
app.include_router(account.router)


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
