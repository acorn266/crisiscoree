@echo off
REM This batch file runs the flood monitor and saves a timestamped log.
REM Used by Windows Task Scheduler to auto-run the check periodically.
REM
REM IMPORTANT: Edit the PLACE_NAME below to your location before scheduling,
REM since Task Scheduler can't type into the interactive prompt for you.

cd /d "%~dp0"
echo Running flood check at %date% %time% >> monitor_log.txt
python monitor_flood_auto.py >> monitor_log.txt 2>&1
echo. >> monitor_log.txt
