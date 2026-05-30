@echo off
title KOGNI Launcher
echo Starting Kogni...
echo.

:: Start API
start "Kogni API" cmd /k "cd /d C:\Users\ivans\Downloads\kogni-final\kogni\kogni-api && uvicorn main:app --reload"

:: Wait for API to start
timeout /t 3 /nobreak > nul

:: Start Dashboard
start "Kogni Dashboard" cmd /k "cd /d C:\Users\ivans\Downloads\kogni-final\kogni\kogni-dashboard && npm run dev"

:: Start Auto Scorer
start "Kogni Scorer" cmd /k "cd /d C:\Users\ivans\Downloads\kogni-final\kogni\kogni-ml && venv\Scripts\activate && python auto_score.py"

echo.
echo All services started.
echo Dashboard: http://localhost:3000
echo API: http://localhost:8000
echo.
pause
