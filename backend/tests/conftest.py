"""Keep backend tests runnable from their documented working directory."""
from __future__ import annotations

import sys
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Test imports must not inherit a deployed/non-debug policy from a developer's
# ignored local .env. Individual configuration tests still construct explicit
# DEBUG=False Settings instances when validating production startup behavior.
os.environ["DEBUG"] = "true"
