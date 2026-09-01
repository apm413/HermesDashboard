@echo off
REM start.bat — запуск HermesDashboard backend (standalone dev)
REM Production: используется как plugin через `hermes plugins install .`
REM
REM Использование:
REM   start.bat              # запуск на 0.0.0.0:5557
REM   HERMES_PORT=5558 start.bat

setlocal
set PORT=%HERMES_PORT%
if "%PORT%"=="" set PORT=5557

set PLUGIN_DIR=%~dp0
set VENV_PY=%PLUGIN_DIR%.venv\Scripts\python.exe

echo Starting HermesDashboard backend on port %PORT%...
cd /d "%PLUGIN_DIR%dashboard"

set HERMES_VIDEO_ROOT=%USERPROFILE%\HermeSvideo
set TIER1_ROOT=%USERPROFILE%\Desktop\tier1-fresh

"%VENV_PY%" -m uvicorn plugin_api:router --host 0.0.0.0 --port %PORT% --log-level info
endlocal