"""all_in_one.py — запуск chrome + скриншот + layout в одном."""
import subprocess, time, json, urllib.request, base64
import websocket

URL = "http://127.0.0.1:5557/"
OUT = r"C:\Users\CarlosRi\HermesDashboard\screenshots\debug.png"

# Убить старые
subprocess.run(["powershell", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True)
time.sleep(1)

# Запустить Chrome
cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    URL,
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("Chrome started, waiting...", flush=True)
time.sleep(7)

# Найти page
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
print("Tabs:", [(t.get("type"), t.get("url","")[:50]) for t in tabs], flush=True)
page = next((t for t in tabs if t.get("type") == "page"), tabs[0])
print("Target URL:", page.get("url"), flush=True)

# Подключаемся и ждём рендер React
ws = websocket.create_connection(page["webSocketDebuggerUrl"])
print("WS connected", flush=True)
time.sleep(8)

# Скриншот
ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
ws.recv()
ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot",
                     "params": {"format": "png", "captureBeyondViewport": False}}))
r = json.loads(ws.recv())
data = base64.b64decode(r["result"]["data"])
open(OUT, "wb").write(data)
print(f"SCREENSHOT: {OUT} ({len(data)} bytes)", flush=True)

# Layout
expr = (
    "JSON.stringify({"
    "viewport: {w: innerWidth, h: innerHeight},"
    "body_h: document.body.scrollHeight,"
    "body_bg: getComputedStyle(document.body).backgroundColor,"
    "root: document.getElementById('root')?.getBoundingClientRect(),"
    "app: document.querySelector('.app')?.getBoundingClientRect() || 'NO .app',"
    "appGrid: document.querySelector('.app') ? getComputedStyle(document.querySelector('.app')).gridTemplateRows : null,"
    "header: document.querySelector('.header')?.getBoundingClientRect() || 'NO .header',"
    "toolbar: document.querySelector('.toolbar')?.getBoundingClientRect() || 'NO .toolbar',"
    "main: document.querySelector('.main')?.getBoundingClientRect() || 'NO .main',"
    "dag: document.querySelector('.dag-wrap')?.getBoundingClientRect() || 'NO .dag-wrap',"
    "h1Text: document.querySelector('h1')?.textContent || 'NO h1'"
    "})"
)
ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": expr}}))
res = json.loads(ws.recv())
print("\n=== LAYOUT ===", flush=True)
print(res["result"]["result"]["value"], flush=True)

ws.close()
proc.terminate()
try: proc.wait(timeout=3)
except: proc.kill()
