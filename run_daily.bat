@echo off
REM Run by Windows Task Scheduler every day
cd /d "%~dp0"
if not exist logs mkdir logs
python main.py >> logs\run.log 2>&1
