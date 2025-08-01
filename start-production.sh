#!/bin/bash

# Production startup script for Break Time Calculator
# This script is used when deploying to production environments like Coolify

echo "🚀 Starting Break Time Calculator in production mode..."

# Set default environment variables if not provided
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}
export SECURE_COOKIES=${SECURE_COOKIES:-true}

# Generate a session secret key if not provided
if [ -z "$SESSION_SECRET_KEY" ]; then
    export SESSION_SECRET_KEY=$(openssl rand -hex 32)
    echo "⚠️  Generated temporary session secret key. Set SESSION_SECRET_KEY environment variable for production!"
fi

# Ensure required directories exist
mkdir -p uploads output data

# Start the application
echo "🌐 Starting server on $HOST:$PORT"
echo "🔒 Secure cookies: $SECURE_COOKIES"

if command -v uv &> /dev/null && [ -f "uv.lock" ]; then
    echo "📦 Using uv for package management"
    uv run uvicorn app.main:app --host $HOST --port $PORT
else
    echo "📦 Using pip/python"
    python -m uvicorn app.main:app --host $HOST --port $PORT
fi
