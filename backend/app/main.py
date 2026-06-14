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

    print("[APP] Server ready!")
    print("=" * 60)

    yield

    # Shutdown
    print("[APP] Shutting down...")


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
