"""Снимает скриншот и сразу выводит layout страницы."""
import subprocess, time, json, urllib.request, base64, os
import websocket

OUT = r"C:\Users\CarlosRi\HermesDashboard\screenshots\current.png"
URL = "http://127.0.0.1:5557/"
W, H = 1920, 1080

# Kill old chrome
subprocess.run(["powershell", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True)
time.sleep(1)

# Start fresh
cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    f"--window-size={W},{H}",
    URL,
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

# Get list
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
target = None
for t in tabs:
    if t.get("type") == "page" and "5557" in t.get("url",""):
        target = t; break
if not target:
    for t in tabs:
        if t.get("type") == "page":
            target = t; break
print("Target:", target.get("url") if target else "none")

if not target:
    print("No target tab!")
    proc.terminate()
    exit(1)

# Use new tab targetId
ws = websocket.create_connection(target["webSocketDebuggerUrl"])

# Enable
ws.send(json.dumps({"id":1, "method":"Page.enable"}))
ws.recv()
ws.send(json.dumps({"id":2, "method":"Runtime.enable"}))
# Drain a few events
ws.recv()
ws.recv()

# Wait for React to mount
print("Waiting 10s for React to mount...")
time.sleep(10)

# Eval layout
expr = """
(function(){
  const app = document.querySelector('.app');
  const header = document.querySelector('.header');
  const toolbar = document.querySelector('.toolbar');
  const main = document.querySelector('.main');
  const firstChild = document.body.firstElementChild;
  const firstChildTag = firstChild ? firstChild.tagName + '#' + (firstChild.id||'') + '.' + (firstChild.className||'') : 'none';
  const root = document.getElementById('root');
  const rootChildren = root ? root.children.length : -1;
  return JSON.stringify({
    bodyH: document.body.scrollHeight,
    winH: window.innerHeight,
    app: app?.getBoundingClientRect(),
    header: header?.getBoundingClientRect(),
    toolbar: toolbar?.getBoundingClientRect(),
    main: main?.getBoundingClientRect(),
    firstChildTag,
    rootChildren,
    rootInnerStart: root ? root.innerHTML.substring(0,200) : 'no root'
  });
})()
"""
ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":expr, "returnByValue":True}}))
# Drain
for _ in range(10):
    try:
        r = ws.recv()
        if '"id":10' in r or '"id": 10' in r:
            break
    except: break
val = json.loads(r).get("result", {}).get("result", {}).get("value", r)
print("LAYOUT:", val)

# Screenshot
ws.send(json.dumps({"id":20, "method":"Page.captureScreenshot",
                     "params":{"format":"png","captureBeyondViewport":False}}))
for _ in range(10):
    try:
        r = ws.recv()
        if '"id":20' in r or '"id": 20' in r:
            break
    except: break
rj = json.loads(r)
data_b64 = rj.get("result", {}).get("data")
if not data_b64:
    print("NO SCREENSHOT DATA, response:", rj)
else:
    data = base64.b64decode(data_b64)
    open(OUT, "wb").write(data)
    print(f"Saved {len(data)} bytes to {OUT}")

ws.close()
proc.terminate()
try: proc.wait(timeout=5)
except: proc.kill()
