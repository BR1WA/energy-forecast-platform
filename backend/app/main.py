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

    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("[DB] Database tables created/verified")

    # Ensure static/avatars directory exists
    os.makedirs("static/avatars", exist_ok=True)

    # Auto-migration: check if users table contains avatar_url
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT avatar_url FROM users LIMIT 1"))
        except Exception:
            print("[DB] Adding avatar_url column to users table...")
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
                conn.commit()
                print("[DB] Column avatar_url added successfully.")
            except Exception as ex:
                print(f"[DB] Error adding avatar_url column: {ex}")

    # Auto-migration: check if users table contains last_activity
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT last_activity FROM users LIMIT 1"))
        except Exception:
            print("[DB] Adding last_activity column to users table...")
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_activity DATETIME"))
                conn.commit()
                print("[DB] Column last_activity added successfully.")
            except Exception as ex:
                print(f"[DB] Error adding last_activity column: {ex}")

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
                email="admin@energyforecast.com",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("[DB] Default admin user created: admin@energyforecast.com / admin123")
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
