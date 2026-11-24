#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  spot2ytm - Spotify to YouTube Music Migrator"
echo "========================================================"
echo ""

# Find Python 3
PY_CMD=""
if command -v python3 &> /dev/null; then
    PY_CMD="python3"
elif command -v python &> /dev/null; then
    PY_CMD="python"
fi

if [ -z "$PY_CMD" ]; then
    echo "[NOTICE] Python 3 was not found."
    echo "Please install Python 3.10+ (e.g., brew install python3 or apt install python3 python3-venv)"
    exit 1
fi

# Set up virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "[1/2] First-time setup: Preparing local environment..."
    $PY_CMD -m venv .venv
    source .venv/bin/activate
    echo "[2/2] Installing lightweight dependencies (takes ~10 seconds)..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo "[OK] Setup completed successfully!"
    echo ""
else
    source .venv/bin/activate
fi

echo "[STARTING] Launching spot2ytm..."
echo "🌐 Your web browser will open automatically in a moment!"
echo ""
python run.py
