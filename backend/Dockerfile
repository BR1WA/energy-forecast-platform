FROM python:3.11-slim AS dependencies

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
ARG INSTALL_TORCH=1
RUN if [ "$INSTALL_TORCH" = "1" ]; then \
      pip install --no-cache-dir -r requirements.txt; \
    else \
      grep -vE '^torch([<>=!~].*)?$' requirements.txt > requirements-no-torch.txt && \
      pip install --no-cache-dir -r requirements-no-torch.txt; \
    fi

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.txt ./requirements-dev.txt
ARG INSTALL_TORCH=1
RUN if [ "$INSTALL_TORCH" = "1" ]; then \
      pip install --no-cache-dir -r requirements-dev.txt; \
    else \
      grep -vE '^-r[[:space:]]+requirements.txt$' requirements-dev.txt > requirements-dev-only.txt && \
      pip install --no-cache-dir -r requirements-dev-only.txt; \
    fi

FROM dependencies AS application

# Copy application code
COPY backend/ .

# Copy training package for imports
COPY training /app/training

# Copy model weights
COPY models /app/models

FROM test-dependencies AS test

COPY backend/ .
COPY training /app/training
COPY models /app/models

CMD ["python", "-m", "pytest", "-q"]

FROM application AS runtime

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
