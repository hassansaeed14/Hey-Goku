@echo off
setlocal enabledelayedexpansion
title AURA
color 0B
cls

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║                                              ║
echo  ║        A  U  R  A                           ║
echo  ║        Autonomous Universal                  ║
echo  ║        Responsive Assistant                  ║
echo  ║                                              ║
echo  ╚══════════════════════════════════════════════╝
echo.
echo  Initializing systems...
echo.

:: ── STEP 1: Check Python ──────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [CRITICAL] Python not found.
    echo  Please install Python 3.10+ from https://python.org
    echo.
    pause
    exit /b 1
)

:: ── STEP 2: Activate Virtual Environment ──────────
if exist D:\HeyGoku\venv\Scripts\activate.bat (
    call D:\HeyGoku\venv\Scripts\activate.bat
) else (
    echo  [SETUP] First time detected. Creating environment...
    cd D:\HeyGoku
    python -m venv venv
    call D:\HeyGoku\venv\Scripts\activate.bat
    echo  [SETUP] Installing dependencies...
    pip install -r D:\HeyGoku\requirements.txt -q
    echo  [SETUP] Done.
)

:: ── STEP 3: Check .env ────────────────────────────
if not exist D:\HeyGoku\.env (
    echo  [WARNING] .env file not found.
    echo  Creating template .env file...
    echo GROQ_API_KEY=your_key_here > D:\HeyGoku\.env
    echo SECRET_KEY=change_this_secret >> D:\HeyGoku\.env
    echo.
    echo  [ACTION NEEDED] Open .env and add your GROQ_API_KEY
    echo  File location: D:\HeyGoku\.env
    echo.
    notepad D:\HeyGoku\.env
    pause
)

:: ── STEP 4: Check Required Folders ───────────────
for %%d in (brain agents memory api interface security config voice logs) do (
    if not exist D:\HeyGoku\%%d\ (
        mkdir D:\HeyGoku\%%d
    )
)
if not exist D:\HeyGoku\memory\locked\ mkdir D:\HeyGoku\memory\locked

:: ── STEP 5: Kill anything on port 5000 ───────────
for /f "tokens=5" %%a in (
    'netstat -ano ^| findstr :5000 2^>nul'
) do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ── STEP 6: Install any missing packages ─────────
echo  Checking packages...
pip install -r D:\HeyGoku\requirements.txt -q 2>nul

:: ── STEP 7: Launch AURA ───────────────────────────
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║  AURA is starting...                         ║
echo  ║  Opening browser in 3 seconds...             ║
echo  ║                                              ║
echo  ║  URL: http://localhost:5000                  ║
echo  ║  To stop AURA: close this window             ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Open browser after 3 second delay in background
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"

:: Start AURA server
cd D:\HeyGoku
python run_aura.py

:: ── If server crashes ─────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║  AURA stopped unexpectedly.                  ║
echo  ║  Check the error above.                      ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
