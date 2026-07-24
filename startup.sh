#!/bin/bash
# Azure App Service startup script for FastAPI with uvicorn

# Start the FastAPI application
# PORT is set by Azure App Service automatically
exec gunicorn app.main:app \
    --bind 0.0.0.0:${PORT:-8000} \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --timeout 120 \
    --access-logfile '-' \
    --error-logfile '-'
