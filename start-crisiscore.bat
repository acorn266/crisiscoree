@echo off
title CrisisCore 2.0

echo ==========================================
echo        CRISISCORE 2.0 STARTUP
echo ==========================================
echo.

echo Starting Backend...
start "CrisisCore Backend" cmd /k "cd /d D:\my projects\crisiscore-disaster-preparedness-2.0\backend && venv\Scripts\python.exe -m uvicorn main:app --reload"

timeout /t 3 /nobreak >nul

echo Starting Frontend...
start "CrisisCore Frontend" cmd /k "cd /d D:\my projects\crisiscore-disaster-preparedness-2.0\frontend && npm run dev"

timeout /t 5 /nobreak >nul

echo Opening CrisisCore...
start http://localhost:5173

echo.
echo ==========================================
echo       CRISISCORE IS STARTING
echo ==========================================
echo.
pause