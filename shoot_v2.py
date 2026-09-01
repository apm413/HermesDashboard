"""shoot_v2.py — chrome devtools screenshot with longer wait + Vite detection."""
import subprocess, time, json, urllib.request, base64, os
import websocket

OUT = r"C:\Users\CarlosRi\HermesDashboard\screenshots\v2-test.png"
URL = "http://127.0.0.1:5557/"
W, H = 1920, 1080

subprocess.run(["powershell", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True)
time.sleep(1)

cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=9222", "--remote-allow-origins=*",
    f"--window-size={W},{H}",
    "--virtual-time-budget=30000",  # 30 сек
    URL,
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)

tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
target = None
for t in tabs:
    if t.get("type") == "page" and "5557" in t.get("url",""):
        target = t; break
if not target:
    for t in tabs:
        if t.get("type") == "page":
            target = t; break
print("Target URL:", target.get("url"))
print("Target ID:", target.get("id"))

ws = websocket.create_connection(target["webSocketDebuggerUrl"])

# Drain initial events
for _ in range(3):
    try: ws.recv()
    except: break

# Wait 8 sec for React + WebSocket
print("Waiting 8s for React mount + WS connect...")
time.sleep(8)

# Check React state
expr = "JSON.stringify({rootChildren: document.getElementById('root')?.children.length, hasError: !!document.querySelector('#root')?.textContent?.includes('error'), errorText: (document.querySelector('#root')?.textContent||'').slice(0,500)})"
ws.send(json.dumps({"id":50, "method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True}}))
for _ in range(5):
    try:
        r = ws.recv()
        if '"id":50' in r or '"id": 50' in r:
            print("REACT STATE:", json.loads(r)["result"]["result"]["value"])
            break
    except: break

# Screenshot
ws.send(json.dumps({"id":99, "method":"Page.captureScreenshot","params":{"format":"png","captureBeyondViewport":False}}))
for _ in range(10):
    try:
        r = ws.recv()
        if '"id":99' in r or '"id": 99' in r:
            break
    except: break
rj = json.loads(r)
b64 = rj.get("result", {}).get("data")
if b64:
    data = base64.b64decode(b64)
    open(OUT, "wb").write(data)
    print(f"Saved {len(data)} bytes to {OUT}")
else:
    print("No screenshot data:", rj)

ws.close()
proc.terminate()
try: proc.wait(timeout=5)
except: proc.kill()
