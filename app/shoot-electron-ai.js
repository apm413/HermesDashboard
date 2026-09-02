// shoot-electron-ai.js — делает скриншот после того как AI ответит в чате
const { app, BrowserWindow } = require('electron');
const path = require('path');

app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-software-rasterizer');

app.whenReady().then(async () => {
    const win = new BrowserWindow({
        width: 1440, height: 900, show: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        }
    });

    await win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
    await new Promise(r => setTimeout(r, 6000));  // models + chat init

    // Отправляем сообщение
    await win.webContents.executeJavaScript(`
        (async () => {
            document.getElementById('chat-text').value = 'Сколько я потратил сегодня?';
            document.getElementById('chat-form').dispatchEvent(new Event('submit', {cancelable: true}));
        })();
    `);

    // Ждём ответа от AI
    await new Promise(r => setTimeout(r, 20000));

    const img = await win.webContents.capturePage();
    const buf = img.toPNG();
    const out = path.join(__dirname, '..', 'screenshots', 'electron-ai-chat.png');
    require('fs').writeFileSync(out, buf);
    console.log(`saved: ${out} (${buf.length} bytes)`);
    app.quit();
});

app.on('window-all-closed', () => app.quit());
