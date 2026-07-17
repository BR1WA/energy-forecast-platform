FROM python:3.11-slim AS dependencies

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

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
