@echo off
REM Hermes Dashboard — start.bat (запуск standalone или Electron-обёртки)
setlocal
set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

if "%1"=="electron" goto electron
if "%1"=="app" goto electron

REM === Standalone: запускаем backend, открываем в браузере ===
echo Starting backend on http://127.0.0.1:5557 ...
start "Hermes Dashboard backend" cmd /c "app\node_modules\.bin\electron.cmd app --no-window 2>nul || .venv\Scripts\python.exe -m uvicorn plugin_api:router --host 127.0.0.1 --port 5557 --log-level warning"
timeout /t 2 /nobreak >nul

REM Открываем dashboard в браузере по умолчанию
start "" "http://127.0.0.1:5557/"

echo.
echo Backend running in separate window.
echo Press Ctrl+C in the backend window to stop.
goto :eof

:electron
REM === Electron-приложение ===
if not exist "app\node_modules\.bin\electron.cmd" (
    echo Installing Electron dependencies (first run)...
    call install.bat
    if errorlevel 1 exit /b 1
)
start "" "app\node_modules\.bin\electron.cmd" app

endlocal
