"""shoot_simple.py — chrome devtools screenshot."""
import subprocess, time, json, urllib.request, base64, os
import websocket

OUT = r"C:\Users\CarlosRi\HermesDashboard\screenshots\current.png"
URL = "http://127.0.0.1:5557/"
W, H = 1920, 1080

subprocess.run(["powershell", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True)
time.sleep(1)

cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    f"--window-size={W},{H}",
    "--virtual-time-budget=15000",
    URL,
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(10)

# Сначала создать новую page
import urllib.request as ur
tabs = json.loads(ur.urlopen("http://127.0.0.1:9222/json").read())
print("All tabs:", [(t.get("id"), t.get("type"), t.get("url","")[:60]) for t in tabs])
target = None
for t in tabs:
    if t.get("type") == "page" and "5557" in t.get("url",""):
        target = t; break
if not target:
    for t in tabs:
        if t.get("type") == "page":
            target = t; break
if not target: target = tabs[0]
print("Target URL:", target.get("url"))
print("Target ID:", target.get("id"))
print("Target WS:", target.get("webSocketDebuggerUrl"))

time.sleep(3)

ws = websocket.create_connection(target["webSocketDebuggerUrl"])
ws.send(json.dumps({"id":1, "method":"Page.enable"}))
ws.recv()
ws.send(json.dumps({"id":2, "method":"Page.captureScreenshot",
                     "params":{"format":"png","captureBeyondViewport":False}}))
result = json.loads(ws.recv())
data = base64.b64decode(result["result"]["data"])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "wb").write(data)
print(f"Saved: {OUT} ({len(data)} bytes)")

expr = (
    "JSON.stringify({"
    "html:document.documentElement.scrollHeight,"
    "body:document.body.scrollHeight,"
    "app:document.querySelector('.app')?.getBoundingClientRect(),"
    "header:document.querySelector('.header')?.getBoundingClientRect(),"
    "toolbar:document.querySelector('.toolbar')?.getBoundingClientRect(),"
    "main:document.querySelector('.main')?.getBoundingClientRect(),"
    "dagWrap:document.querySelector('.dag-wrap')?.getBoundingClientRect(),"
    "firstChild:document.body.firstChild?.outerHTML?.substring(0,200),"
    "winH:window.innerHeight,winW:window.innerWidth"
    "})"
)
ws.send(json.dumps({"id":3, "method":"Runtime.evaluate", "params":{"expression":expr}}))
res = json.loads(ws.recv())
print("LAYOUT:", res["result"]["result"]["value"])

ws.close()
proc.terminate()
try: proc.wait(timeout=5)
except: proc.kill()
