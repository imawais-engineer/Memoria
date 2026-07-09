# Backend image for the Memoria FastAPI app.
FROM python:3.12-slim

# Avoid .pyc files and buffered logs in containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (app package, Celery tasks, and Alembic migrations).
COPY app ./app
COPY celery_app ./celery_app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Production run (no --reload). Override the command to run a Celery worker:
#   celery -A celery_app worker --loglevel=info
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
