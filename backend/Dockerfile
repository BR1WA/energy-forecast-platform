FROM python:3.11-slim AS dependencies

WORKDIR /app

ARG INSTALL_TORCH=1
ARG INSTALL_MONTH_MODEL=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt backend/requirements-ml.txt backend/requirements-foundation.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_TORCH" = "1" ]; then \
      pip install --no-cache-dir -r requirements-ml.txt; \
      if [ "$INSTALL_MONTH_MODEL" = "1" ]; then \
        pip install --no-cache-dir -r requirements-foundation.txt; \
      fi; \
    fi && \
    pip check && \
    python -c "import fastapi, sqlalchemy, uvicorn; from uvicorn.main import main"

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM dependencies AS application
ARG INSTALL_MONTH_MODEL=1

# Copy application code
COPY backend/ .
COPY models/lcl_global_forecasting/month_production_v3/release/ ./model_artifacts/month_production_v3/
RUN if [ "$INSTALL_MONTH_MODEL" = "1" ]; then \
      python scripts/prefetch_month_model.py model_artifacts/month_production_v3; \
    fi

FROM test-dependencies AS test

COPY backend/ .
COPY models/lcl_global_forecasting/month_production_v3/release/ ./model_artifacts/month_production_v3/

CMD ["python", "-m", "pytest", "-q"]

FROM application AS runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
