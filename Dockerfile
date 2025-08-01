# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock* requirements.txt ./

# Install Python dependencies using uv (fallback to pip if uv.lock doesn't exist)
RUN if [ -f "uv.lock" ]; then \
        uv sync --frozen --no-dev; \
    else \
        uv pip install --system -r requirements.txt; \
    fi

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads output static templates data

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port (Coolify will handle port mapping)
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/ || exit 1

# Start command - use environment variables for host and port
CMD ["sh", "-c", "if [ -f 'uv.lock' ]; then uv run uvicorn app.main:app --host $HOST --port $PORT; else python -m uvicorn app.main:app --host $HOST --port $PORT; fi"]
