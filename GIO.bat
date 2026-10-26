@echo off
rem Green Inventory Optimizer - double-click to start. First run installs everything.
title Green Inventory Optimizer
cd /d "%~dp0"

rem Open the browser once the server has had a few seconds to start.
start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://127.0.0.1:8000"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"

echo.
echo GIO has stopped.
pause
