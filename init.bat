@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo   HardwareMonitor-VRChatOSC - First-Time Setup
echo ============================================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/
    echo During installation, check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

FOR /F "tokens=2" %%i IN ('python --version 2^>^&1') DO SET PYTHON_VER=%%i
echo [OK] Python !PYTHON_VER! detected.
echo.

REM --- Check requirements.txt ---
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found.
    echo Make sure you extracted all files from the archive.
    echo.
    pause
    exit /b 1
)

REM --- Create virtual environment ---
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment already exists, skipping creation.
) else (
    echo [INFO] Creating virtual environment .venv...
    python -m venv .venv
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        echo Try running manually: python -m venv .venv
        echo.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)
echo.

REM --- Upgrade pip ---
echo [INFO] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet 2>&1
if !ERRORLEVEL! neq 0 (
    echo [WARN] pip upgrade had issues, continuing anyway...
)
echo [OK] pip is up to date.
echo.

REM --- Install dependencies ---
echo [INFO] Installing dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if !ERRORLEVEL! neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo Please check your internet connection and try again.
    echo You may need to run this script as Administrator for pywin32.
    echo.
    pause
    exit /b 1
)
echo [OK] All dependencies installed.
echo.

REM --- pywin32 post-install ---
echo [INFO] Running pywin32 post-install script...
if exist ".venv\Scripts\pywin32_postinstall.py" (
    .venv\Scripts\python.exe .venv\Scripts\pywin32_postinstall.py -install -silent >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [OK] pywin32 post-install complete.
    ) else (
        echo [WARN] pywin32 post-install may need Administrator privileges.
    )
)
echo.

echo ============================================================
echo   Setup complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Download GPU-Z from:
echo      https://www.techpowerup.com/download/techpowerup-gpu-z/
echo   2. Place GPU-Z.exe in this folder or set path in config.json
echo   3. In GPU-Z: Settings ^> Sensors tab ^> check "Shared Memory"
echo   4. Run start.bat to start monitoring
echo   5. Open VRChat with OSC enabled (default port 9000)
echo.
pause
