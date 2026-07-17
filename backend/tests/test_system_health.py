from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ModelRegistry
from app.routers.system import build_readiness


def make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_readiness_requires_an_active_model():
    db = make_session()
    try:
        result = build_readiness(db)
        assert result["ready"] is False
        assert result["database"]["status"] == "ready"
        assert result["forecast"]["status"] == "not_ready"
    finally:
        db.close()


def test_readiness_checks_model_artifacts(tmp_path: Path):
    db = make_session()
    try:
        for filename in ("model.pt", "pipeline.pkl", "config.yaml"):
            (tmp_path / filename).write_bytes(b"test")
        model = ModelRegistry(
            name="test-model",
            version="1.0.0",
            dataset="test",
            horizon=24,
            experiment_path=str(tmp_path),
            active=True,
        )
        db.add(model)
        db.commit()

        result = build_readiness(db)
        assert result["ready"] is True
        assert result["forecast"]["active_model"] == "test-model"
    finally:
        db.close()
