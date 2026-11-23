#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  spot2ytm - Spotify to YouTube Music Migrator"
echo "========================================================"
echo ""

# Find Python 3
if command -v python3 &> /dev/null; then
    PY_CMD="python3"
elif command -v python &> /dev/null; then
    PY_CMD="python"
else
    echo "[ERROR] Python 3 was not found. Please install Python 3.10+."
    exit 1
fi

# Set up virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "[SETUP] First-time run: Creating virtual environment (.venv)..."
    $PY_CMD -m venv .venv
    source .venv/bin/activate
    echo "[SETUP] Installing dependencies..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt
    echo "[SETUP] Setup complete!"
    echo ""
else
    source .venv/bin/activate
fi

echo "[STARTING] Launching spot2ytm local server..."
echo "🌐 Your browser will open automatically at http://localhost:5000"
echo ""
python run.py
