// shoot-electron.js — запускается Electron, рендерит renderer, делает скриншот,
// пишет в файл и завершает процесс.
//
// Запуск:  electron shoot-electron.js --output=screenshots/electron.png
//
// Использует webContents.capturePage() — это самый стабильный путь
// для оффскрин-рендера, не требует GPU.

const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');

const OUTPUT = (() => {
    const arg = process.argv.find(a => a.startsWith('--output='));
    return arg ? arg.split('=')[1] : path.join(__dirname, '..', 'screenshots', 'electron.png');
})();

app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-software-rasterizer');

app.whenReady().then(async () => {
    const win = new BrowserWindow({
        width: 1440,
        height: 900,
        show: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            offscreen: false,  // используем show:false + capturePage
        },
    });

    // Гарантируем что backend запущен до показа renderer
    const RENDERER = path.join(__dirname, 'renderer', 'index.html');
    console.log('[shoot] loading', RENDERER);
    await win.loadFile(RENDERER);

    // Подождём рендер (React mount + initial fetch)
    await new Promise(r => setTimeout(r, 4000));

    try {
        const img = await win.webContents.capturePage();
        const buf = img.toPNG();
        fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
        fs.writeFileSync(OUTPUT, buf);
        console.log(`[shoot] saved ${OUTPUT} (${buf.length} bytes)`);
    } catch (e) {
        console.error('[shoot] capture failed:', e);
        process.exit(2);
    }

    // Запустим симуляцию чата: кликнем на /help
    try {
        await win.webContents.executeJavaScript(`
            document.getElementById('chat-text').value = '/help';
            document.getElementById('chat-form').dispatchEvent(new Event('submit', {cancelable: true}));
        `);
        await new Promise(r => setTimeout(r, 1500));
        const img2 = await win.webContents.capturePage();
        const buf2 = img2.toPNG();
        const out2 = OUTPUT.replace('.png', '-with-help.png');
        fs.writeFileSync(out2, buf2);
        console.log(`[shoot] saved ${out2} (${buf2.length} bytes)`);
    } catch (e) {
        console.warn('[shoot] chat sim failed:', e.message);
    }

    app.quit();
});

app.on('window-all-closed', () => app.quit());
