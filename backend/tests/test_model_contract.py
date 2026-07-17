from pathlib import Path
import hashlib

import numpy as np

from app.models import ModelRegistry
from app.routers.forecast import build_input_snapshot
from app.services.forecast_service import ForecastService, REQUEST_FEATURE_SCHEMA


def contract_for(tmp_path: Path, *, horizon: int = 24, lookback: int = 96) -> dict:
    fingerprint = hashlib.sha256((tmp_path / "model.pt").read_bytes()).hexdigest()
    return {
        "horizon": horizon,
        "lookback": lookback,
        "target_schema": ["gap"],
        "request_feature_schema": REQUEST_FEATURE_SCHEMA,
        "expected_model_input_shape": [lookback, len(REQUEST_FEATURE_SCHEMA)],
        "accepted_request_shapes": [[lookback, len(REQUEST_FEATURE_SCHEMA)]],
        "artifact_location": "contract-test",
        "fingerprint": fingerprint,
    }


def test_artifact_contract_rejects_incomplete_experiment(tmp_path: Path):
    entry = ModelRegistry(
        name="incomplete", version="1", dataset="test", horizon=24,
        lookback=96, experiment_path=str(tmp_path), active=False,
        artifact_contract={"horizon": 24, "lookback": 96, "target_schema": ["gap"], "artifact_location": "incomplete"},
    )
    violations = ForecastService().validate_artifact_contract(entry)
    assert "missing artifact: model.pt" in violations


def test_artifact_contract_rejects_horizon_mismatch(tmp_path: Path):
    (tmp_path / "model.pt").write_bytes(b"model")
    (tmp_path / "pipeline.pkl").write_bytes(b"pipeline")
    (tmp_path / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("experiment:\n  horizon: 168\nmodel:\n  name: Hybrid_v2\n", encoding="utf-8")
    entry = ModelRegistry(
        name="bad-horizon", version="1", dataset="test", horizon=24, lookback=96,
        experiment_path=str(tmp_path), active=False,
        artifact_contract=contract_for(tmp_path),
        model_fingerprint=hashlib.sha256((tmp_path / "model.pt").read_bytes()).hexdigest(),
    )
    assert ForecastService().validate_artifact_contract(entry) == ["registry horizon does not match config.yaml"]


def test_input_snapshot_is_json_serializable_and_complete():
    snapshot = build_input_snapshot(
        np.array([[1.5], [2.5]], dtype=np.float32),
        np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        ["2026-07-17T10:00:00+00:00", "2026-07-17T11:00:00+00:00"],
    )
    assert snapshot == {
        "target_schema": ["gap"],
        "input_feature_schema": REQUEST_FEATURE_SCHEMA,
        "targets": [[1.5], [2.5]],
        "calendar": [[0.0, 1.0], [1.0, 0.0]],
        "timestamps": ["2026-07-17T10:00:00+00:00", "2026-07-17T11:00:00+00:00"],
    }
