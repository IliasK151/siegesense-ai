@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo          SiegeSense AI - Preview
echo ==========================================
echo.
echo This preview reviews saved Siege recordings.
echo It does not attach to or control the live game.
echo.

where py >nul 2>&1
if errorlevel 1 goto need_python

if not exist ".venv\Scripts\python.exe" goto setup_environment

goto launch_app

:setup_environment
echo First run: setting up the local Python environment...
echo This step needs Python 3.12 and an internet connection.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1"
if errorlevel 1 goto failed

:launch_app
echo.
echo Starting SiegeSense AI...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_windows.ps1"
if errorlevel 1 goto failed
exit /b 0

:need_python
echo Python 3.12 for Windows was not found.
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo Include the Python Launcher, then double-click this file again.
echo.
pause
exit /b 1

:failed
echo.
echo SiegeSense AI did not complete the requested step.
echo Read the error above. You can copy the text and send it in the ChatGPT conversation.
echo.
pause
exit /b 1
