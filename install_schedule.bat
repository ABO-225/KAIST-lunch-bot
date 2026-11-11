@echo off
REM Register run_daily.bat to run every day at 11:30
schtasks /create /tn "KAIST Lunch Bot" /tr "\"%~dp0run_daily.bat\"" /sc daily /st 11:30 /f
echo.
echo Done. To remove: schtasks /delete /tn "KAIST Lunch Bot" /f
pause
