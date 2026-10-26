@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo SiegeSense AI environment was not found.
  echo Double-click START_SIEGESENSE.bat first to install dependencies.
  echo.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_windows.ps1"
if errorlevel 1 (
  echo.
  echo The local test or lint check failed. Copy the error above and send it in the ChatGPT conversation.
  echo.
  pause
  exit /b 1
)

echo.
echo All local checks passed.
pause
exit /b 0
