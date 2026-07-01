#!/usr/bin/env python3
"""Simple web page to send commands to Haseef (the robot's brain).

Run:  .venv/bin/python command_server.py
Open: http://localhost:8080
"""
import asyncio
import json
import logging
import os
import sys
import time

import httpx
from aiohttp import web
from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cmd-srv] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cmd-srv")

# ---------------------------------------------------------------------------
# Prebuilt commands
# ---------------------------------------------------------------------------
PREBUILT = [
    {
        "label": "Grab Water",
        "emoji": "💧",
        "text": "Go to the audience and tell them to come grab water.",
        "color": "#3b82f6",
    },
    {
        "label": "Welcome Audience",
        "emoji": "👋",
        "text": "Welcome everyone who is here and greet them warmly.",
        "color": "#22c55e",
    },
    {
        "label": "Say Goodbye",
        "emoji": "👋",
        "text": "Say goodbye to everyone and thank them for coming.",
        "color": "#a855f7",
    },
    {
        "label": "Tell a Joke",
        "emoji": "😄",
        "text": "Tell a short funny joke to the audience.",
        "color": "#eab308",
    },
    {
        "label": "Be Happy",
        "emoji": "😊",
        "text": "Show a happy expression.",
        "color": "#f97316",
    },
    {
        "label": "Be Sad",
        "emoji": "😢",
        "text": "Show a sad expression.",
        "color": "#64748b",
    },
    {
        "label": "Look Around",
        "emoji": "🔍",
        "text": "Look around the room and tell me what you see.",
        "color": "#06b6d4",
    },
    {
        "label": "Dance",
        "emoji": "💃",
        "text": "Do a little dance!",
        "color": "#ec4899",
    },
    {
        "label": "Introduce Yourself",
        "emoji": "🤖",
        "text": "Introduce yourself to the audience — tell them your name and what you can do.",
        "color": "#14b8a6",
    },
    {
        "label": "Ask for Feedback",
        "emoji": "💬",
        "text": "Ask the audience if they have any questions or feedback.",
        "color": "#8b5cf6",
    },
]

# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hsafa Robot Commander</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    min-height: 100vh;
    padding: 24px;
  }
  h1 {
    font-size: 1.8rem;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 28px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
  }
  .cmd-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 16px;
    border: 1px solid #1e293b;
    border-radius: 14px;
    background: #1e293b;
    color: #e2e8f0;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
  }
  .cmd-btn:hover {
    transform: translateY(-2px);
    border-color: var(--c);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  }
  .cmd-btn:active { transform: translateY(0); }
  .cmd-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
  .cmd-btn .emoji { font-size: 1.6rem; }
  .cmd-btn .label { flex: 1; }
  .cmd-btn .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--c); opacity: 0; transition: opacity 0.2s;
  }
  .cmd-btn.sent .dot { opacity: 1; }
  .custom-section {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .custom-section h2 { font-size: 1.1rem; margin-bottom: 12px; }
  .custom-row { display: flex; gap: 10px; }
  .custom-row input {
    flex: 1;
    padding: 14px 16px;
    border: 1px solid #334155;
    border-radius: 10px;
    background: #0f172a;
    color: #e2e8f0;
    font-size: 1rem;
    outline: none;
  }
  .custom-row input:focus { border-color: #3b82f6; }
  .custom-row button {
    padding: 14px 24px;
    border: none;
    border-radius: 10px;
    background: #3b82f6;
    color: white;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
  }
  .custom-row button:hover { background: #2563eb; }
  .custom-row button:disabled { opacity: 0.4; cursor: not-allowed; }
  .log-section {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 20px;
  }
  .log-section h2 { font-size: 1.1rem; margin-bottom: 12px; }
  #log {
    max-height: 300px;
    overflow-y: auto;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    line-height: 1.6;
  }
  .log-entry {
    padding: 6px 0;
    border-bottom: 1px solid #1e293b;
    display: flex;
    gap: 10px;
  }
  .log-entry .time { color: #64748b; white-space: nowrap; }
  .log-entry .text { color: #e2e8f0; }
  .log-entry.error .text { color: #ef4444; }
  .log-entry.success .text { color: #22c55e; }
  .status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 20px;
    font-size: 0.85rem;
    color: #64748b;
  }
  .status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: #ef4444;
  }
  .status-dot.connected { background: #22c55e; }
</style>
</head>
<body>
  <h1>🤖 Hsafa Robot Commander</h1>
  <p class="subtitle">Send commands to the robot — prebuilt or custom</p>

  <div class="status-bar">
    <div class="status-dot" id="statusDot"></div>
    <span id="statusText">Connecting to Haseef...</span>
  </div>

  <div class="grid" id="grid"></div>

  <div class="custom-section">
    <h2>Custom Command</h2>
    <div class="custom-row">
      <input type="text" id="customInput" placeholder="Type a custom command..." />
      <button id="customBtn" onclick="sendCustom()">Send</button>
    </div>
  </div>

  <div class="log-section">
    <h2>Command Log</h2>
    <div id="log"></div>
  </div>

<script>
const PREBUILT = __PREBUILT__;
const grid = document.getElementById('grid');
const logEl = document.getElementById('log');
const customInput = document.getElementById('customInput');
const customBtn = document.getElementById('customBtn');

// Build prebuilt buttons
PREBUILT.forEach((cmd, i) => {
  const btn = document.createElement('button');
  btn.className = 'cmd-btn';
  btn.style.setProperty('--c', cmd.color);
  btn.innerHTML = `
    <span class="emoji">${cmd.emoji}</span>
    <span class="label">${cmd.label}</span>
    <span class="dot"></span>
  `;
  btn.onclick = () => sendCommand(cmd.text, btn);
  grid.appendChild(btn);
});

function addLog(text, type) {
  const entry = document.createElement('div');
  entry.className = 'log-entry ' + (type || '');
  const now = new Date().toLocaleTimeString();
  entry.innerHTML = `<span class="time">${now}</span><span class="text">${text}</span>`;
  logEl.prepend(entry);
}

async function sendCommand(text, btn) {
  if (btn) {
    btn.disabled = true;
    btn.classList.remove('sent');
  }
  addLog('Sending: ' + text, '');
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    const data = await res.json();
    if (data.ok) {
      addLog('✓ Sent: ' + text, 'success');
      if (btn) {
        btn.classList.add('sent');
        setTimeout(() => btn.classList.remove('sent'), 2000);
      }
    } else {
      addLog('✗ Error: ' + (data.error || 'unknown'), 'error');
    }
  } catch (e) {
    addLog('✗ Failed: ' + e.message, 'error');
  }
  if (btn) btn.disabled = false;
}

async function sendCustom() {
  const text = customInput.value.trim();
  if (!text) return;
  customBtn.disabled = true;
  await sendCommand(text, null);
  customInput.value = '';
  customBtn.disabled = false;
}

customInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendCustom();
});

// Check status
async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (data.connected) {
      dot.className = 'status-dot connected';
      txt.textContent = 'Connected to Haseef: ' + (data.name || data.haseef_id);
    } else {
      dot.className = 'status-dot';
      txt.textContent = 'Disconnected';
    }
  } catch (e) {}
}
checkStatus();
setInterval(checkStatus, 5000);
</script>
</body>
</html>""".replace("__PREBUILT__", json.dumps(PREBUILT))


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
class CommandServer:
    def __init__(self, sdk: HsafaSDK, haseef_id: str, port: int = 8080):
        self.sdk = sdk
        self.haseef_id = haseef_id
        self.port = port
        self.haseef_name: str = ""

    async def start(self):
        # Fetch Haseef name for status display
        try:
            h = await self.sdk.haseef.get(self.haseef_id)
            self.haseef_name = h.get("name", "HsafaRobot")
            log.info("Connected to Haseef: %s (%s)", self.haseef_name, self.haseef_id)
        except Exception as e:
            log.warning("Could not fetch Haseef info: %s", e)

        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_post("/api/send", self._handle_send)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        log.info("Command server running on http://localhost:%d", self.port)

    async def _handle_index(self, request):
        return web.Response(text=HTML, content_type="text/html")

    async def _handle_status(self, request):
        return web.json_response({
            "connected": True,
            "name": self.haseef_name,
            "haseef_id": self.haseef_id,
        })

    async def _handle_send(self, request):
        try:
            body = await request.json()
            text = (body.get("text") or "").strip()
            if not text:
                return web.json_response({"ok": False, "error": "text is required"})

            log.info("Sending command: %s", text[:100])
            await self.sdk.push_event({
                "type": "user_message",
                "data": {
                    "text": text,
                    "source": "command_web",
                },
                "haseefId": self.haseef_id,
            })
            log.info("Command sent OK: %s", text[:80])
            return web.json_response({"ok": True})
        except httpx.TimeoutException:
            log.error("push_event timeout: %s", text[:80] if 'text' in dir() else '?')
            return web.json_response({"ok": False, "error": "timeout"})
        except Exception as e:
            log.error("push_event failed: %s", e)
            return web.json_response({"ok": False, "error": str(e)})


async def main():
    core_url = os.environ.get("HSAFA_CORE_URL", "https://core.hsafa.com")
    core_key = os.environ.get("HSAFA_CORE_KEY", "")
    haseef_id = os.environ.get("HASEEF_ID", "")

    if not core_key:
        print("Error: HSAFA_CORE_KEY not set. Add it to .env", file=sys.stderr)
        sys.exit(1)
    if not haseef_id:
        print("Error: HASEEF_ID not set. Add it to .env", file=sys.stderr)
        sys.exit(1)

    port = int(os.environ.get("COMMAND_PORT", "8080"))

    sdk = HsafaSDK(SdkOptions(
        core_url=core_url,
        api_key=core_key,
        skill="robot_base",
    ))

    # Patch timeout (same as main.py)
    _timeout = httpx.Timeout(30.0, connect=10.0)

    async def _request_with_timeout(self, method, path, body=None):
        url = f"{self.core_url}{path}"
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        response = await self._client.request(
            method, url, headers=headers, json=body, timeout=_timeout
        )
        if not response.is_success:
            raise Exception(
                f"{method} {path} failed ({response.status_code}): {response.text}"
            )
        if response.status_code == 204 or not response.content:
            return None
        if "application/json" in response.headers.get("content-type", ""):
            return response.json()
        return None

    sdk._request = _request_with_timeout.__get__(sdk, HsafaSDK)

    # Connect SSE
    log.info("Connecting to Haseef SSE stream...")
    sse_task = asyncio.create_task(sdk.connect(), name="haseef-sse")
    await asyncio.sleep(1)

    server = CommandServer(sdk, haseef_id, port)
    await server.start()

    # Keep running
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        log.info("Shutting down...")
        await sdk.disconnect()
        sse_task.cancel()
        try:
            await sse_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
