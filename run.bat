@echo off
title spot2ytm - Spotify to YouTube Music Migrator
setlocal enabledelayedexpansion

echo ========================================================
echo   spot2ytm - Spotify to YouTube Music Migrator
echo ========================================================
echo.

:: Detect Python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=python
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PY_CMD=py -3
    ) else (
        echo [ERROR] Python was not found in your PATH.
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
)

:: Virtual environment setup
if not exist ".venv\Scripts\activate.bat" (
    echo [SETUP] First-time run: Creating virtual environment (.venv)...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SETUP] Installing dependencies (this only happens once)...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [SETUP] Setup complete!
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: Launch spot2ytm
echo [STARTING] Launching spot2ytm local server...
echo 🌐 Your browser will open automatically at http://localhost:5000
echo.
python run.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTICE] Application terminated with code %ERRORLEVEL%.
    pause
)
