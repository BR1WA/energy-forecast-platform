"""Offline, checksum-verified inference for the production 30-day model."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import numpy as np

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


class MonthProductionForecaster:
    """Load the pinned Chronos-2 adapter and return calibrated daily quantiles."""

    def __init__(self, release_dir: Path | str, device: str = "cpu") -> None:
        import torch
        from chronos import Chronos2Pipeline
        from huggingface_hub import snapshot_download

        self.release_dir = Path(release_dir).resolve()
        self.manifest = json.loads(
            (self.release_dir / "manifest.json").read_text(encoding="utf-8")
        )
        adapter = self.release_dir / self.manifest["adapter"]["filename"]
        if self._sha256(adapter) != self.manifest["adapter"]["sha256"]:
            raise RuntimeError("The monthly LoRA adapter checksum is invalid.")
        if self.manifest["contract"]["inference_dtype"] != "float32":
            raise RuntimeError("The monthly release contract requires FP32 inference.")

        base = self.manifest["base_model"]
        try:
            snapshot = Path(
                snapshot_download(
                    repo_id=base["model_id"],
                    revision=base["revision"],
                    allow_patterns=["config.json", "model.safetensors"],
                    local_files_only=True,
                )
            )
        except Exception as exc:
            raise RuntimeError(
                "The pinned Chronos-2 base model is not cached. "
                "Build the production image with INSTALL_MONTH_MODEL=1."
            ) from exc
        if self._sha256(snapshot / "model.safetensors") != base["model_sha256"]:
            raise RuntimeError("The pinned Chronos-2 base-model checksum is invalid.")

        self.pipeline = Chronos2Pipeline.from_pretrained(
            self.release_dir,
            device_map=device,
            dtype=torch.float32,
            local_files_only=True,
            # PEFT 0.20 blocks dynamic adapter mappings unless the exact local
            # model module is explicitly trusted. The adapter and base weights
            # above are both pinned and checksum-verified before this import.
            import_allowlist=["chronos.chronos2.model"],
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _context(self, history: Iterable[float]) -> np.ndarray:
        values = np.asarray(list(history), dtype=np.float32)
        minimum = int(self.manifest["contract"]["minimum_observed_days"])
        context = int(self.manifest["contract"]["context_days"])
        finite = np.isfinite(values)
        if int(finite.sum()) < minimum:
            raise ValueError(f"At least {minimum} finite daily values are required.")
        positions = np.arange(len(values))
        values = np.interp(positions, positions[finite], values[finite]).astype(
            np.float32
        )
        values = values[-context:]
        if len(values) < context:
            values = np.pad(values, (context - len(values), 0), mode="edge")
        return values

    def _calibrate(self, prediction: np.ndarray, context: np.ndarray) -> np.ndarray:
        scale = max(float(np.mean(np.abs(np.diff(context[-90:])))), 1e-6)
        calibration = self.manifest["calibration"]
        prediction[0, :, 0] = np.maximum(
            0,
            prediction[0, :, 0] - float(calibration["lower_offset"]) * scale,
        )
        prediction[0, :, 2] += float(calibration["upper_offset"]) * scale
        return np.sort(np.maximum(prediction, 0), axis=2)

    def predict(self, history: Iterable[float]) -> dict[str, list[float]]:
        context = self._context(history)
        quantiles, _ = self.pipeline.predict_quantiles(
            [context],
            prediction_length=int(self.manifest["contract"]["horizon_days"]),
            quantile_levels=self.manifest["contract"]["quantiles"],
            batch_size=1,
            cross_learning=False,
        )
        raw = quantiles[0].float().cpu().numpy()
        calibrated = self._calibrate(raw, context)[0]
        return {
            "p10": calibrated[:, 0].tolist(),
            "p50": calibrated[:, 1].tolist(),
            "p90": calibrated[:, 2].tolist(),
        }
