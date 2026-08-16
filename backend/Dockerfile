FROM python:3.11-slim@sha256:a630a63cdb314e2d138a2fca3e375e319e8568346ffafac5b980f888630ac4f1 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

FROM base AS dependencies

ARG INSTALL_TORCH=1
ARG INSTALL_MONTH_MODEL=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/* && \
    python -m venv /opt/venv

COPY backend/requirements.lock backend/requirements-ml.lock backend/requirements-foundation.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && \
    if [ "$INSTALL_TORCH" = "1" ]; then \
      if [ "$INSTALL_MONTH_MODEL" = "1" ]; then \
        pip install --no-cache-dir --require-hashes -r requirements-foundation.lock; \
      else \
        pip install --no-cache-dir --require-hashes -r requirements-ml.lock; \
      fi; \
    fi && \
    pip check && \
    if [ "$INSTALL_TORCH" = "1" ] && [ "$INSTALL_MONTH_MODEL" = "1" ]; then \
      python -c "import transformers, peft; from chronos import Chronos2Pipeline"; \
    fi && \
    python -c "import fastapi, sqlalchemy, uvicorn; from uvicorn.main import main"

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.lock ./requirements-dev.lock
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.lock && pip check

FROM base AS application

ARG INSTALL_TORCH=1
ARG INSTALL_MONTH_MODEL=1
ENV HF_HOME=/app/.cache/huggingface

RUN groupadd --system --gid 10001 appuser && \
    useradd --system --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser

COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=appuser:appuser backend/ .
COPY --chown=appuser:appuser models/lcl_global_forecasting/month_production_v3/release/ ./model_artifacts/month_production_v3/
RUN if [ "$INSTALL_TORCH" = "1" ] && [ "$INSTALL_MONTH_MODEL" = "1" ]; then \
      python scripts/prefetch_month_model.py model_artifacts/month_production_v3; \
    fi && \
    chown -R appuser:appuser /app

FROM application AS test

COPY --from=test-dependencies /opt/venv /opt/venv
USER appuser
CMD ["python", "-m", "pytest", "-q"]

FROM application AS runtime

USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
