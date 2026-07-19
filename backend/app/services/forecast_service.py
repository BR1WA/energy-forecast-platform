"""
Forecast service — registry-based lazy-loading with a full public API.

Public surface expected by the routers
───────────────────────────────────────
  ForecastService.get_available_models()      → List[dict]  (ModelInfo-shaped)
  ForecastService.get_sample_datasets()       → List[dict]  (SampleDataset-shaped)
  ForecastService.samples                     → dict        (keyed by sample name)
  ForecastService.predict(model_name, ...)    → (np.ndarray, List[dict])
  ForecastService.predict_comparison(...)     → Dict[str, np.ndarray]
  ForecastService.load_active_model(db)       → bool        (used by health-check / startup)

  generate_calendar_features(hours, days, months) → np.ndarray  (imported by router)
"""

from __future__ import annotations

import json
import os
import hashlib
import inspect
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    import torch
except ModuleNotFoundError:  # Allows non-inference CI tests to run in a lean image.
    torch = None
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import ModelRegistry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_COLS = ["gap"]
REQUEST_FEATURE_SCHEMA = [
    "gap", "grp", "voltage", "current", "sub_metering_1", "sub_metering_2", "sub_metering_3",
]

# The experiments directory is mounted into the container at /app/experiments.
EXPERIMENTS_DIR = os.environ.get("EXPERIMENTS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "experiments"))


# ---------------------------------------------------------------------------
# Module-level helpers (imported by the routers)
# ---------------------------------------------------------------------------

def generate_calendar_features(
    hours: np.ndarray,
    days: np.ndarray,
    months: np.ndarray,
) -> np.ndarray:
    """Return cyclical calendar features for a sequence of timestamps.

    Output shape: (N, 6) — [sin_h, cos_h, sin_d, cos_d, sin_m, cos_m]
    """
    sin_hour  = np.sin(2 * np.pi * hours / 24)
    cos_hour  = np.cos(2 * np.pi * hours / 24)
    sin_day   = np.sin(2 * np.pi * days / 7)
    cos_day   = np.cos(2 * np.pi * days / 7)
    sin_month = np.sin(2 * np.pi * (months - 1) / 12)
    cos_month = np.cos(2 * np.pi * (months - 1) / 12)
    return np.stack(
        [sin_hour, cos_hour, sin_day, cos_day, sin_month, cos_month], axis=1
    ).astype(np.float32)


def _display_name(exp_name: str) -> str:
    """Convert an experiment directory name to a human-readable label."""
    lower = exp_name.lower()
    horizon = "24h"
    for h in ("168", "720"):
        if h in lower:
            horizon = f"{h}h"
            break
    if "hybrid" in lower:
        return f"Hybrid V2 ({horizon})"
    if "itransformer" in lower:
        return f"iTransformer ({horizon})"
    # Fallback: title-case after replacing underscores, capped at 40 chars
    return exp_name.replace("_", " ").title()[:40]


def _architecture(exp_name: str) -> str:
    lower = exp_name.lower()
    if "hybrid" in lower:
        return "Hybrid (CNN + BiLSTM + Attention)"
    if "itransformer" in lower:
        return "iTransformer"
    return "Unknown"


# ---------------------------------------------------------------------------
# ForecastService
# ---------------------------------------------------------------------------

class ForecastService:
    """Registry-backed inference service with lazy model loading.

    A single model is kept in memory at a time. When a request arrives for a
    different model the previous one is evicted and the new one loaded.  The
    identity of the cached model is tracked by its registry ``id``.
    """

    def __init__(self) -> None:
        self._cached_model_id: Optional[int] = None
        self._model = None
        self._pipeline: Optional[Any] = None
        self._config: Optional[dict] = None
        self.device = None
        if torch is not None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Lazy-loaded sample datasets
        self._samples: Optional[Dict[str, Any]] = None

    # ── Registry helpers ────────────────────────────────────────────────────

    def _seed_registry_from_disk(self, db: Session) -> None:
        """Synchronize the database registry with the experiments directory.
        
        Reads metadata from `metrics.json` and updates the registry if the file has 
        been modified. Never automatically sets a model to active.
        """
        if not os.path.isdir(EXPERIMENTS_DIR):
            return

        required_files = ("model.pt", "pipeline.pkl", "config.yaml", "metrics.json")
        for root, dirs, files in os.walk(EXPERIMENTS_DIR):
            if not all(f in files for f in required_files):
                continue
                
            exp_path = root
            exp_folder_name = os.path.basename(root)
            
            try:
                metrics_path = os.path.join(exp_path, "metrics.json")
                mtime = os.path.getmtime(metrics_path)
                
                import yaml
                import json
                from datetime import datetime, timezone
                with open(os.path.join(exp_path, "config.yaml")) as fh:
                    cfg = yaml.safe_load(fh)
                with open(metrics_path) as fh:
                    summary = json.load(fh)

                # Parse Phase 3 vs Legacy config
                exp_meta = cfg.get("experiment", {})
                architecture_config = cfg.get("architecture", {}) or cfg.get("model", {})
                exp_id = exp_meta.get("id", None)
                exp_name = exp_meta.get("name", exp_folder_name)
                dataset_name = exp_meta.get("dataset", "ihepc")
                horizon = int(exp_meta.get("horizon") or architecture_config.get("forecast_horizon") or 24)
                lookback = int(exp_meta.get("lookback") or architecture_config.get("lookback") or 96)
                
                # Check if it already exists in the DB (by name, as name must be unique)
                entry = db.query(ModelRegistry).filter(ModelRegistry.name == exp_name).first()
                if (
                    entry
                    and entry.updated_at
                    and entry.updated_at.timestamp() >= mtime
                    and entry.artifact_contract
                    and entry.artifact_contract.get("expected_model_input_shape") == [lookback, len(REQUEST_FEATURE_SCHEMA)]
                ):
                    continue  # Already up to date

                m = summary.get("final_unscaled") or summary.get("metrics", {}).get("final_unscaled") or summary.get("final") or summary.get("metrics", {}).get("final", {})
                contract = {
                    "architecture": cfg.get("architecture", {}).get("name") or cfg.get("model", {}).get("name"),
                    "dataset": dataset_name,
                    "horizon": horizon,
                    "lookback": lookback,
                    "sampling_interval": "1h",
                    "target_schema": TARGET_COLS,
                    "request_feature_schema": REQUEST_FEATURE_SCHEMA,
                    "target_unit": "kW",
                    "preprocessing": {"artifact": "pipeline.pkl", "feature_schema": ["gap"]},
                    "required_files": list(required_files),
                    "artifact_location": os.path.relpath(exp_path, EXPERIMENTS_DIR),
                    "evaluation_metrics": m,
                    "expected_model_input_shape": [lookback, len(REQUEST_FEATURE_SCHEMA)],
                    "accepted_request_shapes": [[lookback, len(REQUEST_FEATURE_SCHEMA)]],
                    "expected_output_shape": [horizon, len(TARGET_COLS)],
                    "fingerprint": summary.get("model_fingerprint"),
                }
                
                if entry:
                    # Update existing entry
                    entry.version = cfg.get("version", "1.0.0")
                    entry.experiment_id = exp_id
                    entry.dataset = dataset_name
                    entry.horizon = horizon
                    entry.lookback = lookback
                    entry.model_fingerprint = summary.get("model_fingerprint")
                    entry.mae = m.get("mae")
                    entry.rmse = m.get("rmse")
                    entry.artifact_contract = contract
                    entry.contract_validated_at = datetime.now(timezone.utc)
                    entry.updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
                else:
                    # Create new entry
                    entry = ModelRegistry(
                        name=exp_name,
                        version=cfg.get("version", "1.0.0"),
                        experiment_id=exp_id,
                        dataset=dataset_name,
                        horizon=horizon,
                        lookback=lookback,
                        experiment_path=exp_path,
                        model_fingerprint=summary.get("model_fingerprint"),
                        artifact_contract=contract,
                        contract_validated_at=datetime.now(timezone.utc),
                        active=False,  # Never auto-activate
                        mae=m.get("mae"),
                        rmse=m.get("rmse"),
                        created_at=datetime.fromtimestamp(mtime, tz=timezone.utc),
                        updated_at=datetime.fromtimestamp(mtime, tz=timezone.utc)
                    )
                    db.add(entry)
            except Exception as e:
                import logging
                logging.error(f"Failed to sync experiment {exp_folder_name}: {e}")
                continue

        db.commit()

    def validate_artifact_contract(self, entry: ModelRegistry) -> list[str]:
        """Return contract violations before an artifact can be served or activated."""
        if not entry.artifact_contract:
            return ["artifact contract metadata is missing"]
        required = ("model.pt", "pipeline.pkl", "config.yaml", "metrics.json")
        missing = [name for name in required if not os.path.isfile(os.path.join(entry.experiment_path, name))]
        if missing:
            return [f"missing artifact: {name}" for name in missing]
        try:
            import yaml
            with open(os.path.join(entry.experiment_path, "config.yaml")) as handle:
                config = yaml.safe_load(handle) or {}
            with open(os.path.join(entry.experiment_path, "metrics.json")) as handle:
                metrics = json.load(handle)
            configured_horizon = (
                config.get("experiment", {}).get("horizon")
                or config.get("architecture", {}).get("forecast_horizon")
                or config.get("model", {}).get("forecast_horizon")
                or config.get("forecast_horizon")
            )
            if configured_horizon is not None and int(configured_horizon) != entry.horizon:
                return ["registry horizon does not match config.yaml"]
            if not (config.get("architecture", {}).get("name") or config.get("model", {}).get("name")):
                return ["architecture name missing from config.yaml"]
            if not isinstance(metrics, dict):
                return ["metrics.json must contain an object"]
            contract = entry.artifact_contract
            if contract.get("horizon") != entry.horizon or contract.get("lookback") != entry.lookback:
                return ["artifact contract does not match registry horizon or lookback"]
            if contract.get("target_schema") != TARGET_COLS:
                return ["artifact contract target schema is unsupported"]
            if contract.get("request_feature_schema") != REQUEST_FEATURE_SCHEMA:
                return ["artifact contract request feature schema is unsupported"]
            if contract.get("expected_model_input_shape") != [entry.lookback, len(REQUEST_FEATURE_SCHEMA)]:
                return ["artifact contract model input shape is invalid"]
            if contract.get("accepted_request_shapes") != [[entry.lookback, len(REQUEST_FEATURE_SCHEMA)]]:
                return ["artifact contract accepted request shapes are invalid"]
            if os.path.isabs(contract.get("artifact_location", "")):
                return ["artifact contract must use a portable relative location"]
            with open(os.path.join(entry.experiment_path, "model.pt"), "rb") as handle:
                model_fingerprint = hashlib.file_digest(handle, "sha256").hexdigest()
            if model_fingerprint != contract.get("fingerprint") or model_fingerprint != entry.model_fingerprint:
                return ["model.pt fingerprint does not match registry metadata"]
        except Exception as exc:
            return [f"invalid model metadata: {type(exc).__name__}"]
        return []

    def sync_registry(self, db: Session) -> None:
        """Refresh registry metadata and ensure startup has a deployable model."""
        self._seed_registry_from_disk(db)
        active_entries = db.query(ModelRegistry).filter(ModelRegistry.active.is_(True)).all()
        for entry in active_entries:
            if self.validate_artifact_contract(entry):
                entry.active = False
        db.flush()

        active_pairs = {
            (entry.dataset, entry.horizon)
            for entry in db.query(ModelRegistry).filter(ModelRegistry.active.is_(True)).all()
        }
        candidates = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.active.is_(False))
            .order_by(ModelRegistry.updated_at.desc(), ModelRegistry.id.desc())
            .all()
        )
        for entry in candidates:
            pair = (entry.dataset, entry.horizon)
            if pair in active_pairs or self.validate_artifact_contract(entry):
                continue
            try:
                self.warm_model(entry)
            except Exception:
                continue
            entry.active = True
            active_pairs.add(pair)
        db.commit()

    def _resolve_entry(self, model_name: str, horizon: int, db: Session) -> ModelRegistry:
        """Resolve an exact registered model; never substitute an active model."""
        entry = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.name == model_name,
                ModelRegistry.horizon == horizon,
                ModelRegistry.active.is_(True),
            )
            .first()
        )
        if entry is None:
            raise ValueError(f"No active model named '{model_name}' supports the {horizon}h horizon.")
        violations = self.validate_artifact_contract(entry)
        if violations:
            raise ValueError(f"Model '{model_name}' is not deployable: {'; '.join(violations)}")
        return entry

    # ── Model loading ────────────────────────────────────────────────────────

    def _ensure_loaded(self, entry: ModelRegistry) -> None:
        """Load model and pipeline from *entry* into memory if not already cached."""
        if torch is None or self.device is None:
            raise RuntimeError("PyTorch is required for forecast inference but is not installed in this environment.")
        if self._cached_model_id == entry.id:
            return

        # Keep the training package out of the API/test import path. It is only
        # needed when a real inference request loads an artifact.
        from training.features.feature_engineering import FeaturePipeline

        exp_path = entry.experiment_path
        model_path    = os.path.join(exp_path, "model.pt")
        pipeline_path = os.path.join(exp_path, "pipeline.pkl")
        config_path   = os.path.join(exp_path, "config.yaml")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model artifact not found: {model_path}")

        import yaml
        with open(config_path) as fh:
            config = yaml.safe_load(fh)
        self._config = config

        pipeline = FeaturePipeline(time_col="timestamp", target_cols=["gap"])
        pipeline.load(pipeline_path)
        self._pipeline = pipeline

        arch = config.get("architecture", {}).get("name") or config.get("model", {}).get("name")
        if not arch:
            raise ValueError("Architecture name missing from config.yaml")

        from app.ml.model_registry import get_model_class
        ModelClass = get_model_class(arch)
        
        # Load kwargs
        model_kwargs = config.get("architecture", config.get("model", {}))
        if isinstance(model_kwargs, dict) and "name" in model_kwargs:
            model_kwargs = model_kwargs.copy()
            del model_kwargs["name"]
        
        if arch in ("Hybrid_v2", "HybridV2", "iTransformer"):
            # These legacy models expect the full config dict
            model = ModelClass(config.get("model", {}))
        else:
            accepted_parameters = inspect.signature(ModelClass.__init__).parameters
            model_kwargs = {
                key: value
                for key, value in model_kwargs.items()
                if key in accepted_parameters
            }
            model = ModelClass(**model_kwargs)

        model.to(self.device)
        model.load(model_path, self.device)
        model.eval()

        self._model = model
        self._cached_model_id = entry.id

    def warm_model(self, entry: ModelRegistry) -> None:
        """Load a validated registry entry so readiness proves inference can start."""
        self._ensure_loaded(entry)

    def load_active_model(self, db: Session) -> bool:
        """Load the currently active model.  Returns True if one was found."""
        entry = db.query(ModelRegistry).filter(ModelRegistry.active == True).first()
        if not entry:
            return False
        if self.validate_artifact_contract(entry):
            return False
        self._ensure_loaded(entry)
        return True

    def get_active_model_registry(self, db: Session) -> Optional[ModelRegistry]:
        """Return the currently active ModelRegistry entry, if any."""
        return db.query(ModelRegistry).filter(ModelRegistry.active == True).first()

    # ── Public API ───────────────────────────────────────────────────────────


    def get_available_models(self) -> List[dict]:
        """Return every registered experiment as a ``ModelInfo``-compatible dict."""
        db = SessionLocal()
        try:
            self._seed_registry_from_disk(db)
            entries = (
                db.query(ModelRegistry)
                .order_by(ModelRegistry.created_at.desc())
                .all()
            )
            result = []
            for entry in entries:
                training_metrics = None
                summary_path = os.path.join(entry.experiment_path, "metrics.json")
                if os.path.exists(summary_path):
                    try:
                        with open(summary_path) as fh:
                            summary = json.load(fh)
                        m = summary.get("final_unscaled") or summary.get("metrics", {}).get("final_unscaled") or summary.get("final") or summary.get("metrics", {}).get("final", {})
                        training_metrics = {
                            "mae":     float(m.get("mae",  0.0)),
                            "rmse":    float(m.get("rmse", 0.0)),
                            "mape":    float(m.get("mape", 0.0)),
                            "r2_score": float(m.get("r2",  0.0)),
                        }
                    except Exception:
                        pass

                result.append({
                    "id":                str(entry.id),
                    "name":              entry.name,
                    "display_name":      _display_name(entry.name),
                    "architecture_type": _architecture(entry.name),
                    "description":       f"Experiment: {entry.name}",
                    "training_metrics":  training_metrics,
                    "is_active":         entry.active,
                    "version":           entry.version,
                    # accuracy is a proxy: invert normalised MAE (capped at [0, 1])
                    "accuracy":          round(max(0.0, 1.0 - (entry.mae or 0.5)), 4),
                    "last_trained":      (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                    "parameters": {"forecast_horizon": str(entry.horizon), "lookback": str(entry.lookback or "")},
                    "status": "invalid" if self.validate_artifact_contract(entry) else ("active" if entry.active else "inactive"),
                })
            return result
        finally:
            db.close()

    def get_sample_datasets(self) -> List[dict]:
        """Return metadata about the built-in sample datasets."""
        return [
            {
                "name":        key,
                "description": val["description"],
                "season":      val["season"],
                "date_range":  val["date_range"],
            }
            for key, val in self.samples.items()
        ]

    @property
    def samples(self) -> Dict[str, Any]:
        """Lazy-loaded sample datasets keyed by name."""
        if self._samples is None:
            self._samples = self._load_samples()
        return self._samples

    # ── Inference ────────────────────────────────────────────────────────────

    def predict(
        self,
        model_name: str,
        targets: np.ndarray,
        calendar: Optional[np.ndarray] = None,
        threshold_kw: float = 3.0,
        start_hour: Optional[int] = None,
        horizon: int = 24,
        timestamps=None,
    ) -> Tuple[np.ndarray, List[dict]]:
        """Run inference for a named model on pre-sliced input arrays.

        Parameters
        ----------
        model_name:
            Registry entry name to use.  Falls back to the active model if
            not found.
        targets:
            Shape ``(lookback,)`` or ``(lookback, N)``.  Column 0 is always
            Global Active Power (GAP) in kW.
        calendar:
            Ignored — the ``FeaturePipeline`` derives all calendar features
            from the timestamp index.  Accepted for call-site compatibility.
        timestamps:
            Timestamps aligned with *targets*.  When ``None`` a synthetic
            lookback window ending at *now* (UTC) is used.

        Returns
        -------
        predictions : np.ndarray, shape ``(horizon, num_targets)``
        alerts      : List[dict]
        """
        # 1. Resolve and load the requested model
        db = SessionLocal()
        try:
            self._seed_registry_from_disk(db)
            entry = self._resolve_entry(model_name, horizon, db)
            self._ensure_loaded(entry)
        finally:
            db.close()

        # 2. Map input targets to pipeline expected columns
        cols = self._pipeline.target_cols if self._pipeline.target_cols else ["gap"]
        
        mapping_indices = {
            "Global_active_power": 0,
            "Global_reactive_power": 1,
            "Voltage": 2,
            "Global_intensity": 3,
            "Sub_metering_1": 4,
            "Sub_metering_2": 5,
            "Sub_metering_3": 6,
            "gap": 0,
            "grp": 1,
            "voltage": 2,
            "gi": 3,
            "current": 3,
            "sub_metering_1": 4,
            "sub_metering_2": 5,
            "sub_metering_3": 6
        }

        # 3. Build a timestamp index
        if timestamps is not None:
            ts = pd.DatetimeIndex(timestamps)
            if ts.tz is None:
                ts = ts.tz_localize("UTC")
        else:
            ts = pd.date_range(
                end=pd.Timestamp.now(tz="UTC"),
                periods=len(targets),
                freq="h",
            )

        data_dict = {"timestamp": ts}
        for col in cols:
            idx = mapping_indices.get(col, 0)
            if targets.ndim > 1 and idx < targets.shape[1]:
                val = targets[:, idx]
            else:
                val = targets[:, 0] if targets.ndim > 1 else targets
            data_dict[col] = val.astype(np.float32)

        raw_df = pd.DataFrame(data_dict)

        # 4. Repair scale_cols if loaded as empty [] (pickle compatibility fix)
        if not self._pipeline.scale_cols:
            self._pipeline.scale_cols = [c for c in raw_df.columns if c != "timestamp"]

        # Run through FeaturePipeline
        missing_strat = self._config.get("training", {}).get("missing_strategy", "interpolate") if self._config else "interpolate"
        processed = self._pipeline.transform(
            raw_df, validate=True, missing_strategy=missing_strat
        )

        lookback = 96
        if self._config:
            lookback = self._config.get("model", {}).get("lookback") or self._config.get("architecture", {}).get("lookback", 96)
        processed = processed.tail(lookback)


        if len(processed) < lookback:
            raise ValueError(
                f"Not enough data: need {lookback} rows, got {len(processed)}."
            )

        # 5. Build tensors (cols maintains correct features dimension)
        x = (
            torch.tensor(processed[cols].values, dtype=torch.float32)
            .unsqueeze(0).to(self.device)
        )
        if calendar is not None:
            calendar_values = np.asarray(calendar, dtype=np.float32)[-lookback:]
        else:
            calendar_index = pd.DatetimeIndex(ts[-lookback:])
            calendar_values = generate_calendar_features(
                calendar_index.hour.values,
                calendar_index.dayofweek.values,
                calendar_index.month.values,
            )
        if calendar_values.shape != (lookback, 6):
            raise ValueError(f"Calendar features must be [{lookback}, 6], got {calendar_values.shape}.")
        temp = (
            torch.tensor(calendar_values, dtype=torch.float32)
            .unsqueeze(0).to(self.device)
        )

        # 6. Forward pass
        with torch.no_grad():
            preds = self._model.predict(x, temp)

        preds_np: np.ndarray = preds.cpu().numpy()[0]   # (horizon, num_targets)
        
        # 7. Inverse transform to return real kW values
        if hasattr(self._pipeline, 'scaler'):
            preds_np = self._pipeline.scaler.inverse_transform(preds_np)

        # The bundled models are multi-channel, but the user-facing product
        # forecasts Global Active Power (GAP) only.
        if preds_np.ndim > 1:
            preds_np = preds_np[:, :1]

        # Ensure Global Active Power (column 0) is never negative
        if preds_np.ndim > 1:
            preds_np[:, 0] = np.clip(preds_np[:, 0], 0.01, None)
        else:
            preds_np = np.clip(preds_np, 0.01, None)
            
        alerts = self._check_alerts(preds_np, threshold_kw)
        return preds_np, alerts


    def predict_comparison(
        self,
        targets: np.ndarray,
        calendar: Optional[np.ndarray] = None,
        horizon: int = 24,
        timestamps=None,
    ) -> Dict[str, np.ndarray]:
        """Run ``predict`` for every registered model.

        Models that fail to load or infer are silently skipped.  Callers
        always receive at least one result or a ``ValueError`` if the registry
        is empty.
        """
        db = SessionLocal()
        try:
            self._seed_registry_from_disk(db)
            names = [
                e.name for e in db.query(ModelRegistry).filter(
                    ModelRegistry.horizon == horizon,
                    ModelRegistry.active.is_(True),
                ).all()
            ]
        finally:
            db.close()

        if not names:
            raise ValueError(
                "No models registered. "
                "Train a model and register it via POST /api/v1/models."
            )

        results: Dict[str, np.ndarray] = {}
        for name in names:
            try:
                preds, _ = self.predict(
                    name, targets, calendar=calendar,
                    horizon=horizon, timestamps=timestamps,
                )
                results[name] = preds
            except Exception:
                continue   # skip models with missing artifacts or config errors
        return results

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _check_alerts(
        self, predictions: np.ndarray, threshold_kw: float = 3.0
    ) -> List[dict]:
        """Return a list of alert dicts if the predicted peak exceeds the threshold."""
        gap_preds = predictions[:, 0]
        peak = float(np.max(gap_preds))
        if peak <= threshold_kw:
            return []
        severity = "high" if peak > threshold_kw * 1.5 else "medium"
        return [
            {
                "alert_type": "peak_demand",
                "severity": severity,
                "message": (
                    f"Predicted peak demand of {peak:.2f} kW "
                    f"exceeds threshold of {threshold_kw:.1f} kW"
                ),
                "peak_kw": peak,
            }
        ]

    # ── Sample loading ───────────────────────────────────────────────────────

    def _load_samples(self) -> Dict[str, Any]:
        """Load sample datasets from the UCI CSV or fall back to synthetic data."""
        candidates = [
            "/app/data/household_power_consumption.txt",
            os.path.join(
                os.path.dirname(__file__),
                "../../../data/household_power_consumption.txt",
            ),
        ]
        data_path = next((p for p in candidates if os.path.exists(p)), None)
        if data_path:
            result = self._samples_from_csv(data_path)
            if result:
                return result
        return self._synthetic_samples()

    def _samples_from_csv(self, path: str) -> Dict[str, Any]:
        """Extract summer and winter 96-h slices from the UCI household dataset."""
        try:
            df = pd.read_csv(path, sep=";", na_values=["?"], low_memory=False)
            df["datetime"] = pd.to_datetime(
                df["Date"] + " " + df["Time"], dayfirst=True
            )
            df = (
                df.dropna(subset=["Global_active_power"])
                .rename(columns={"Global_active_power": "gap"})
                .set_index("datetime")
                .sort_index()
            )
            df = df.resample("h").mean(numeric_only=True)
            df["gap"] = df["gap"].interpolate(method="time")
            df.index = df.index.tz_localize("UTC")

            lookback = 96   # 4 days

            def _slice(start: str, description: str, season: str, date_range: str):
                ts_start = pd.Timestamp(start, tz="UTC")
                ts_end   = ts_start + pd.Timedelta(hours=lookback - 1)
                chunk = df.loc[ts_start:ts_end, "gap"]
                if len(chunk) < lookback:
                    return None
                gap = chunk.values[:lookback].astype(np.float32)
                ts  = chunk.index[:lookback]
                return {
                    "targets":     gap.reshape(-1, 1),
                    "calendar":    None,   # FeaturePipeline handles features
                    "start_hour":  int(ts[0].hour),
                    "input_start": ts[0].to_pydatetime(),
                    "input_end":   ts[-1].to_pydatetime(),
                    "timestamps":  ts,
                    "description": description,
                    "season":      season,
                    "date_range":  date_range,
                }

            samples: Dict[str, Any] = {}
            summer = _slice(
                "2007-08-06 00:00",
                "Summer week — high AC load, low heating.",
                "Summer", "Aug 6–9, 2007",
            )
            winter = _slice(
                "2008-01-07 00:00",
                "Winter week — peak heating demand.",
                "Winter", "Jan 7–10, 2008",
            )
            if summer:
                samples["sample_summer"] = summer
            if winter:
                samples["sample_winter"] = winter
            return samples
        except Exception:
            return {}

    def _synthetic_samples(self) -> Dict[str, Any]:
        """Generate two deterministic 96-h profiles as a fallback."""
        rng = np.random.default_rng(42)
        ts_summer = pd.date_range("2007-08-06", periods=96, freq="h", tz="UTC")
        ts_winter = pd.date_range("2008-01-07", periods=96, freq="h", tz="UTC")

        def _profile(ts, base: float, scale: float) -> np.ndarray:
            h = np.array([t.hour for t in ts])
            v = base + scale * np.sin(np.pi * h / 24) + rng.normal(0, 0.05, 96)
            return np.clip(v, 0.1, None).astype(np.float32)

        def _make(ts, gap, description, season, date_range):
            return {
                "targets":     gap.reshape(-1, 1),
                "calendar":    None,
                "start_hour":  int(ts[0].hour),
                "input_start": ts[0].to_pydatetime(),
                "input_end":   ts[-1].to_pydatetime(),
                "timestamps":  ts,
                "description": description,
                "season":      season,
                "date_range":  date_range,
            }

        return {
            "sample_summer": _make(
                ts_summer, _profile(ts_summer, 0.8, 0.6),
                "Synthetic summer profile (fallback).", "Summer", "Aug 2007",
            ),
            "sample_winter": _make(
                ts_winter, _profile(ts_winter, 1.8, 0.9),
                "Synthetic winter profile (fallback).", "Winter", "Jan 2008",
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_forecast_service: Optional[ForecastService] = None


def get_forecast_service() -> ForecastService:
    """Return (or create) the module-level singleton."""
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
