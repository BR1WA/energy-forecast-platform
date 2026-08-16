"""Keep backend tests runnable from their documented working directory."""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest
import sqlalchemy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Test imports must not inherit a deployed/non-debug policy from a developer's
# ignored local .env. Individual configuration tests still construct explicit
# DEBUG=False Settings instances when validating production startup behavior.
os.environ["DEBUG"] = "true"


# Python 3.13 reports unclosed sqlite3 connections when test-local SQLAlchemy
# engines are left to garbage collection. Tests deliberately create many
# isolated in-memory engines, so retain and dispose every one deterministically
# after the session. Patching before test-module collection also covers engines
# created at module import time.
_original_create_engine = sqlalchemy.create_engine
_test_engines: list[sqlalchemy.engine.Engine] = []


def _tracked_create_engine(*args: object, **kwargs: object) -> sqlalchemy.engine.Engine:
    engine = _original_create_engine(*args, **kwargs)
    _test_engines.append(engine)
    return engine


sqlalchemy.create_engine = _tracked_create_engine


@pytest.fixture(scope="session", autouse=True)
def dispose_test_engines():
    yield
    for engine in reversed(_test_engines):
        engine.dispose()
