"""debug_layout.py — зайти в dashboard, снять скриншот, выгрузить размеры."""
import json, urllib.request, base64, time, sys
import websocket

tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
page = next((t for t in tabs if t.get("type") == "page"), tabs[0])
print("URL:", page.get("url"), flush=True)

ws = websocket.create_connection(page["webSocketDebuggerUrl"])

# Подождать чтобы React отрендерил
time.sleep(8)

# 1) Скриншот
ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
ws.recv()
ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot",
                     "params": {"format": "png", "captureBeyondViewport": False}}))
result = json.loads(ws.recv())
data = base64.b64decode(result["result"]["data"])
out = r"C:\Users\CarlosRi\HermesDashboard\screenshots\debug.png"
open(out, "wb").write(data)
print(f"SCREENSHOT: {out} ({len(data)} bytes)", flush=True)

# 2) Layout
expr = (
    "JSON.stringify({"
    "viewport: {w: innerWidth, h: innerHeight},"
    "body_h: document.body.scrollHeight,"
    "body_bg: getComputedStyle(document.body).backgroundColor,"
    "html_overflow: getComputedStyle(document.documentElement).overflow,"
    "body_overflow: getComputedStyle(document.body).overflow,"
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
print("\n=== LAYOUT ===")
print(res["result"]["result"]["value"], flush=True)

ws.close()
