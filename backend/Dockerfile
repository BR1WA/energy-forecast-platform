FROM python:3.11-slim AS dependencies

WORKDIR /app

ARG INSTALL_TORCH=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt backend/requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_TORCH" = "1" ]; then \
      pip install --no-cache-dir -r requirements-ml.txt; \
    fi

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM dependencies AS application

# Copy application code
COPY backend/ .

FROM test-dependencies AS test

COPY backend/ .

CMD ["python", "-m", "pytest", "-q"]

FROM application AS runtime

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
