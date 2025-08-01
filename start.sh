#!/bin/bash
echo "Starting Break Time Calculator Web Application..."
echo
echo "Installing/syncing dependencies with uv..."
uv sync
echo
echo "Starting the web server..."
echo "Open your browser and go to: http://127.0.0.1:8000"
echo
echo "Press Ctrl+C to stop the server"
echo
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
