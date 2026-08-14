"""Cache and verify the exact Chronos-2 base weights during the image build."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    release_dir = Path(sys.argv[1]).resolve()
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    base = manifest["base_model"]
    snapshot = Path(
        snapshot_download(
            repo_id=base["model_id"],
            revision=base["revision"],
            allow_patterns=["config.json", "model.safetensors"],
        )
    )
    actual = sha256(snapshot / "model.safetensors")
    if actual != base["model_sha256"]:
        raise SystemExit(
            f"Chronos-2 checksum mismatch: expected {base['model_sha256']}, got {actual}."
        )
    print(f"Cached verified {base['model_id']} at revision {base['revision']}.")


if __name__ == "__main__":
    main()
