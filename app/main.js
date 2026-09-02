// main.js — Electron main process для Hermes Dashboard
// Запускает backend (uvicorn) если он не отвечает на 5557,
// открывает окно с двумя панелями: dashboard (слева) + чат (справа).
const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');

// === Конфиг ===
const APP_ROOT = path.resolve(__dirname, '..');
const DASHBOARD_DIR = path.join(APP_ROOT, 'dashboard');
const PYTHON_EXE = process.platform === 'win32'
  ? path.join(APP_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(APP_ROOT, '.venv', 'bin', 'python');
const BACKEND_URL = 'http://127.0.0.1:5557';
const BACKEND_PORT = 5557;
const STARTUP_TIMEOUT_MS = 15000;

let mainWindow = null;
let backendProcess = null;
let isQuitting = false;

// === Helpers ===
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(path.join(app.getPath('logs'), 'app.log'), line); } catch (e) {}
  if (process.stdout) process.stdout.write(line);
}

function checkBackend() {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_URL + '/system', (res) => resolve(res.statusCode === 200));
    req.on('error', () => resolve(false));
    req.setTimeout(1500, () => { req.destroy(); resolve(false); });
  });
}

async function waitForBackend(maxMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < maxMs) {
    if (await checkBackend()) return true;
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

function spawnBackend() {
  if (!fs.existsSync(PYTHON_EXE)) {
    dialog.showErrorBox(
      'Hermes Dashboard — venv не найден',
      `Не найден интерпретатор:\n${PYTHON_EXE}\n\nЗапустите install.bat из корня проекта или создайте venv вручную:\n\n  python -m venv .venv\n  .venv\\Scripts\\pip install -r requirements.txt`
    );
    return null;
  }
  log(`spawning backend: ${PYTHON_EXE} -m uvicorn plugin_api:router --port ${BACKEND_PORT}`);
  const proc = spawn(
    PYTHON_EXE,
    ['-m', 'uvicorn', 'plugin_api:router', '--host', '127.0.0.1', '--port', String(BACKEND_PORT), '--log-level', 'warning'],
    { cwd: DASHBOARD_DIR, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }
  );
  proc.stdout.on('data', d => log(`[backend] ${d.toString().trim()}`));
  proc.stderr.on('data', d => log(`[backend-err] ${d.toString().trim()}`));
  proc.on('exit', (code, sig) => {
    log(`backend exited code=${code} sig=${sig}`);
    if (!isQuitting && mainWindow) {
      dialog.showMessageBox(mainWindow, {
        type: 'warning',
        title: 'Backend остановлен',
        message: 'Backend-сервер завершил работу.',
        detail: `Код выхода: ${code}. Перезапустите приложение.`
      });
    }
  });
  return proc;
}

function killBackend() {
  if (backendProcess && !backendProcess.killed) {
    log(`killing backend PID ${backendProcess.pid}`);
    try { backendProcess.kill(); } catch (e) { log(`kill err: ${e.message}`); }
  }
}

// === Окно ===
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: '#050810',
    show: false,
    title: 'Hermes Dashboard',
    icon: path.join(__dirname, 'build', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => mainWindow.show());

  mainWindow.on('closed', () => { mainWindow = null; });

  // Внешние ссылки открываем в системном браузере
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

// === IPC: чат-панель → backend ===
ipcMain.handle('chat:send', async (_evt, text) => {
  return new Promise((resolve) => {
    const data = JSON.stringify({ text });
    const req = http.request(BACKEND_URL + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
    }, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { resolve({ ok: false, error: 'bad-json', body }); }
      });
    });
    req.on('error', e => resolve({ ok: false, error: e.message }));
    req.write(data);
    req.end();
  });
});

ipcMain.handle('chat:commands', async () => {
  return new Promise((resolve) => {
    http.get(BACKEND_URL + '/chat/commands', (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { resolve({ ok: false, error: 'bad-json' }); }
      });
    }).on('error', e => resolve({ ok: false, error: e.message }));
  });
});

ipcMain.handle('app:info', () => ({
  app_root: APP_ROOT,
  python_exe: PYTHON_EXE,
  backend_url: BACKEND_URL,
  platform: process.platform,
  electron: process.versions.electron,
  chrome: process.versions.chrome,
  node: process.versions.node,
  user: os.userInfo().username,
}));

ipcMain.handle('window:reload-dashboard', () => {
  if (mainWindow) {
    const iframe = mainWindow.webContents.executeJavaScript(`
      document.querySelector('iframe.dashboard-iframe')?.contentWindow.location.reload();
    `);
    return iframe && 'ok';
  }
  return 'no-window';
});

// === Lifecycle ===
app.whenReady().then(async () => {
  // 1) Сначала проверяем, не запущен ли уже backend (standalone-режим)
  if (!(await checkBackend())) {
    backendProcess = spawnBackend();
    log('waiting for backend to be ready…');
    const ready = await waitForBackend(STARTUP_TIMEOUT_MS);
    if (!ready) {
      dialog.showErrorBox(
        'Hermes Dashboard — backend не стартовал',
        `Backend не отвечает на ${BACKEND_URL} после ${STARTUP_TIMEOUT_MS/1000} сек.\n\nПроверьте .venv и requirements.txt.`
      );
    } else {
      log('backend ready');
    }
  } else {
    log('backend already running (standalone mode)');
  }
  createWindow();
});

app.on('window-all-closed', () => {
  isQuitting = true;
  killBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  isQuitting = true;
  killBackend();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
