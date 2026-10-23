@echo off
title CrisisCore 2.0

rem Runs from wherever this file lives, so the project folder can be moved or renamed.
set "ROOT=%~dp0"

echo ==========================================
echo        CRISISCORE 2.0 STARTUP
echo ==========================================
echo.

if not exist "%ROOT%backend\venv\Scripts\python.exe" (
    echo [ERROR] backend\venv not found. See DEMO_CHECKLIST.md, "One-time setup".
    pause
    exit /b 1
)
if not exist "%ROOT%frontend\node_modules" (
    echo [ERROR] frontend\node_modules not found. Run "npm install" in the frontend folder.
    pause
    exit /b 1
)
if not exist "%ROOT%backend\.env" (
    echo [WARNING] backend\.env not found - weather will be unavailable and the chatbot
    echo           will use offline answers. Copy backend\.env.example to backend\.env.
    echo.
)

echo Starting Backend on http://localhost:8000 ...
start "CrisisCore Backend" cmd /k "cd /d "%ROOT%backend" && venv\Scripts\python.exe -m uvicorn main:app --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Frontend on http://localhost:5173 ...
start "CrisisCore Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --port 5173 --strictPort"

timeout /t 5 /nobreak >nul

echo Opening CrisisCore...
start http://localhost:5173

echo.
echo ==========================================
echo       CRISISCORE IS STARTING
echo ==========================================
echo.
pause
