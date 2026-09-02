@echo off
REM Hermes Dashboard — install.bat
REM Устанавливает Electron и зависимости для app/
setlocal

set "APP_DIR=%~dp0app"
set "REPO_ROOT=%~dp0"

echo === Hermes Dashboard installer ===
echo.

REM 1) Python venv для backend
if not exist "%REPO_ROOT%.venv\Scripts\python.exe" (
    echo [1/3] Creating Python venv...
    python -m venv "%REPO_ROOT%.venv"
    if errorlevel 1 (
        echo ERROR: failed to create venv. Make sure Python 3.10+ is on PATH.
        exit /b 1
    )
    "%REPO_ROOT%.venv\Scripts\pip.exe" install -r "%REPO_ROOT%requirements.txt"
) else (
    echo [1/3] Python venv already exists.
)

REM 2) Node.js + Electron
where node >nul 2>nul
if errorlevel 1 (
    echo [2/3] ERROR: Node.js not found on PATH. Install from https://nodejs.org/
    echo         Then run this script again.
    exit /b 1
)
echo [2/3] Node.js found: 
node --version

if not exist "%APP_DIR%\node_modules\electron" (
    echo [2/3] Installing Electron + electron-builder...
    pushd "%APP_DIR%"
    call npm install
    popd
) else (
    echo [2/3] Electron already installed.
)

REM 3) Создаём ярлык на рабочем столе
echo [3/3] Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\Hermes Dashboard.lnk"
set "TARGET=%REPO_ROOT%app\node_modules\.bin\electron.cmd"
set "ICON=%REPO_ROOT%app\build\icon.ico"
set "WORKDIR=%REPO_ROOT%app"

powershell -NoProfile -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
    "$s.TargetPath = '%TARGET%';" ^
    "$s.WorkingDirectory = '%WORKDIR%';" ^
    "$s.IconLocation = '%ICON%';" ^
    "$s.Description = 'Hermes Dashboard — Steampunk monitoring';" ^
    "$s.Save()"

echo.
echo === Installation complete ===
echo.
echo To start: double-click "Hermes Dashboard" on your desktop.
echo Or run:  start.bat
echo.
echo The Electron app will start the backend automatically on port 5557.
endlocal
