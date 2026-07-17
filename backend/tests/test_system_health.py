from pathlib import Path
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ModelRegistry
from app.routers.system import build_readiness
from app.services.forecast_service import REQUEST_FEATURE_SCHEMA, get_forecast_service


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


def test_readiness_warms_a_validated_model(tmp_path: Path, monkeypatch):
    db = make_session()
    try:
        for filename in ("model.pt", "pipeline.pkl"):
            (tmp_path / filename).write_bytes(b"test")
        (tmp_path / "config.yaml").write_text(
            "architecture:\n  name: TestModel\n  forecast_horizon: 24\n", encoding="utf-8"
        )
        (tmp_path / "metrics.json").write_text("{}", encoding="utf-8")
        fingerprint = hashlib.sha256((tmp_path / "model.pt").read_bytes()).hexdigest()
        model = ModelRegistry(
            name="test-model",
            version="1.0.0",
            dataset="test",
            horizon=24,
            lookback=96,
            experiment_path=str(tmp_path),
            artifact_contract={
                "horizon": 24,
                "lookback": 96,
                "target_schema": ["gap"],
                "request_feature_schema": REQUEST_FEATURE_SCHEMA,
                "expected_model_input_shape": [96, len(REQUEST_FEATURE_SCHEMA)],
                "accepted_request_shapes": [[96, len(REQUEST_FEATURE_SCHEMA)]],
                "artifact_location": "test-model",
                "fingerprint": fingerprint,
            },
            model_fingerprint=fingerprint,
            active=True,
        )
        db.add(model)
        db.commit()
        warmed = []
        monkeypatch.setattr(get_forecast_service(), "warm_model", lambda entry: warmed.append(entry.id))

        result = build_readiness(db)
        assert result["ready"] is True
        assert result["forecast"]["active_model"] == "test-model"
        assert warmed == [model.id]
    finally:
        db.close()


def test_readiness_rejects_a_model_that_cannot_warm(tmp_path: Path, monkeypatch):
    db = make_session()
    try:
        for filename in ("model.pt", "pipeline.pkl"):
            (tmp_path / filename).write_bytes(b"test")
        (tmp_path / "config.yaml").write_text(
            "architecture:\n  name: TestModel\n  forecast_horizon: 24\n", encoding="utf-8"
        )
        (tmp_path / "metrics.json").write_text("{}", encoding="utf-8")
        fingerprint = hashlib.sha256((tmp_path / "model.pt").read_bytes()).hexdigest()
        db.add(ModelRegistry(
            name="unloadable-model", version="1.0.0", dataset="unloadable", horizon=24,
            lookback=96, experiment_path=str(tmp_path), active=True, model_fingerprint=fingerprint,
            artifact_contract={
                "horizon": 24, "lookback": 96, "target_schema": ["gap"],
                "request_feature_schema": REQUEST_FEATURE_SCHEMA,
                "expected_model_input_shape": [96, len(REQUEST_FEATURE_SCHEMA)],
                "accepted_request_shapes": [[96, len(REQUEST_FEATURE_SCHEMA)]],
                "artifact_location": "unloadable-model", "fingerprint": fingerprint,
            },
        ))
        db.commit()
        monkeypatch.setattr(get_forecast_service(), "warm_model", lambda entry: (_ for _ in ()).throw(RuntimeError("broken")))

        result = build_readiness(db)
        assert result["ready"] is False
        assert result["forecast"]["missing_artifacts"] == ["model warm-up failed: RuntimeError"]
    finally:
        db.close()
