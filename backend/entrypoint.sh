#!/bin/sh
# Apply pending database migrations, then start the API.
# Migrations are intentionally run here rather than from application code, so a
# schema change is an explicit, observable deploy step.
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
