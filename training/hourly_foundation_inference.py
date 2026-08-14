"""Checksum-verified inference for hourly Chronos-2 challenger releases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import numpy as np

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


class HourlyFoundationForecaster:
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
            raise RuntimeError("The hourly LoRA adapter checksum is invalid.")
        base = self.manifest["base_model"]
        snapshot = Path(
            snapshot_download(
                repo_id=base["model_id"],
                revision=base["revision"],
                allow_patterns=["config.json", "model.safetensors"],
                local_files_only=True,
            )
        )
        if self._sha256(snapshot / "model.safetensors") != base["model_sha256"]:
            raise RuntimeError("The pinned Chronos-2 base-model checksum is invalid.")
        self.pipeline = Chronos2Pipeline.from_pretrained(
            self.release_dir,
            device_map=device,
            dtype=torch.float32,
            local_files_only=True,
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
        required = int(self.manifest["contract"]["minimum_observed_hours"])
        if len(values) < required or not np.isfinite(values[-required:]).all():
            raise ValueError(f"At least {required} finite hourly values are required.")
        return values[-required:]

    def predict(self, history: Iterable[float]) -> dict[str, list[float]]:
        context = self._context(history)
        contract = self.manifest["contract"]
        quantiles, _ = self.pipeline.predict_quantiles(
            [context],
            prediction_length=int(contract["horizon_hours"]),
            quantile_levels=contract["quantiles"],
            batch_size=1,
            cross_learning=False,
        )
        raw = np.maximum(quantiles[0].float().cpu().numpy(), 0)
        scale = max(float(np.mean(np.abs(np.diff(context[-168:])))), 1e-6)
        calibration = self.manifest["calibration"]
        raw[0, :, 0] = np.maximum(
            0, raw[0, :, 0] - float(calibration["lower_offset"]) * scale
        )
        raw[0, :, 2] += float(calibration["upper_offset"]) * scale
        calibrated = np.sort(raw, axis=2)[0]
        return {
            "p10": calibrated[:, 0].tolist(),
            "p50": calibrated[:, 1].tolist(),
            "p90": calibrated[:, 2].tolist(),
        }
