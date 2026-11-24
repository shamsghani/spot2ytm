@echo off
title spot2ytm - Spotify to YouTube Music Migrator
setlocal enabledelayedexpansion

echo ========================================================
echo   spot2ytm - Spotify to YouTube Music Migrator
echo ========================================================
echo.

:: 1. Check if Python is installed
set PY_CMD=
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=python
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PY_CMD=py -3
    )
)

if "%PY_CMD%"=="" (
    echo [NOTICE] Python was not found on your system.
    echo.
    echo Opening Python download page in your browser...
    start https://www.python.org/downloads/
    echo.
    echo Please follow these 2 quick steps:
    echo   1. Run the downloaded installer.
    echo   2. IMPORTANT: Check the box "Add Python to PATH" at the bottom!
    echo   3. Once finished, double-click this run.bat again.
    echo.
    pause
    exit /b 1
)

:: 2. Set up local virtual environment if needed
if not exist ".venv\Scripts\activate.bat" (
    echo [1/2] First-time setup: Preparing local environment...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Could not create virtual environment.
        echo Please ensure Python is properly installed and try again.
        pause
        exit /b 1
    )
    echo [2/2] Installing lightweight dependencies (takes ~10 seconds)...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Setup completed successfully!
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: 3. Launch application
echo [STARTING] Launching spot2ytm...
echo 🌐 Your web browser will open automatically in a moment!
echo.
python run.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTICE] Application closed with code %ERRORLEVEL%.
    pause
)
