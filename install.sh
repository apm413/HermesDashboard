#!/usr/bin/env bash
# Hermes Dashboard — install.sh (Linux/Mac)
set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$REPO_ROOT/app"

echo "=== Hermes Dashboard installer ==="
echo

# 1) Python venv
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
    echo "[1/3] Creating Python venv..."
    python3 -m venv "$REPO_ROOT/.venv"
    "$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/requirements.txt"
else
    echo "[1/3] Python venv already exists."
fi

# 2) Node.js + Electron
if ! command -v node >/dev/null 2>&1; then
    echo "[2/3] ERROR: Node.js not found. Install from https://nodejs.org/"
    exit 1
fi
echo "[2/3] Node.js $(node --version)"

if [ ! -d "$APP_DIR/node_modules/electron" ]; then
    echo "[2/3] Installing Electron + electron-builder..."
    (cd "$APP_DIR" && npm install)
else
    echo "[2/3] Electron already installed."
fi

# 3) Desktop entry (.desktop file)
echo "[3/3] Creating desktop entry..."
DESKTOP="$HOME/Desktop/Hermes Dashboard.desktop"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Name=Hermes Dashboard
Comment=Steampunk real-time dashboard for AI agent pipelines
Exec="$APP_DIR/node_modules/.bin/electron" "$APP_DIR"
Icon=$APP_DIR/build/icon.png
Terminal=false
Type=Application
Categories=Development;Monitor;
EOF
chmod +x "$DESKTOP"

echo
echo "=== Installation complete ==="
echo
echo "To start: double-click Hermes Dashboard on your desktop,"
echo "or run:  ./start.sh"
