"""dashboard_server.py — WebSocket server that pushes dashboard layouts to the React app.

Runs on ws://localhost:8765. Supports two modes:
1. Bulk: push_layout() — send entire layout at once (show_visual tool)
2. Incremental: push_init() + push_add_component() — build screen piece by piece
   (dashboard_init / dashboard_add tools)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import websockets

log = logging.getLogger("dashboard_server")

_HOST = "localhost"
_PORT = 8765

_server: Optional["DashboardServer"] = None


class DashboardServer:
    def __init__(self) -> None:
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._server: Optional[websockets.WebSocketServer] = None

    async def start(self) -> None:
        self._server = await websockets.serve(self._handler, _HOST, _PORT)
        log.info("[Dashboard] WebSocket server listening on ws://%s:%d", _HOST, _PORT)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        log.info("[Dashboard] WebSocket server stopped.")

    async def _handler(self, ws: websockets.WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        log.info("[Dashboard] Client connected (%d total)", len(self._clients))
        try:
            await ws.wait_closed()
        finally:
            self._clients.discard(ws)
            log.info("[Dashboard] Client disconnected (%d total)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            log.debug("[Dashboard] No clients connected — message dropped")
            return
        payload = json.dumps(message, ensure_ascii=False, default=str)
        tasks = [asyncio.create_task(c.send(payload)) for c in self._clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def push_layout(self, layout: dict[str, Any]) -> None:
        await self.broadcast({"action": "render", "layout": layout})
        log.info("[Dashboard] Pushed layout: %s (%d components)",
                 layout.get("title", "?"), len(layout.get("components", [])))

    async def push_init(self, title: str, subtitle: str, columns: int) -> None:
        await self.broadcast({
            "action": "init",
            "layout": {"title": title, "subtitle": subtitle, "columns": columns, "components": []},
        })
        log.info("[Dashboard] Init dashboard: %s (cols=%d)", title, columns)

    async def push_add_component(self, component: dict[str, Any]) -> None:
        await self.broadcast({"action": "add", "component": component})
        log.info("[Dashboard] Added component: %s", component.get("type", "?"))

    async def push_status(self, status: str, text: str = "") -> None:
        await self.broadcast({"action": "status", "status": status, "text": text})

    async def push_clear(self) -> None:
        await self.broadcast({"action": "clear"})


async def get_server() -> DashboardServer:
    global _server
    if _server is None:
        _server = DashboardServer()
        await _server.start()
    return _server


def push_layout_sync(layout: dict[str, Any]) -> None:
    """Sync wrapper — schedules push_layout on the running event loop."""
    if _server is None:
        log.warning("[Dashboard] Server not started — layout dropped")
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_server.push_layout(layout))
    except RuntimeError:
        log.warning("[Dashboard] No running loop — layout dropped")


def push_status_sync(status: str, text: str = "") -> None:
    """Sync wrapper — schedules push_status on the running event loop."""
    if _server is None:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_server.push_status(status, text))
    except RuntimeError:
        pass


def push_init_sync(title: str, subtitle: str = "", columns: int = 2) -> None:
    """Sync wrapper — schedules push_init on the running event loop."""
    if _server is None:
        log.warning("[Dashboard] Server not started — init dropped")
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_server.push_init(title, subtitle, columns))
    except RuntimeError:
        log.warning("[Dashboard] No running loop — init dropped")


def push_add_component_sync(component: dict[str, Any]) -> None:
    """Sync wrapper — schedules push_add_component on the running event loop."""
    if _server is None:
        log.warning("[Dashboard] Server not started — component dropped")
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_server.push_add_component(component))
    except RuntimeError:
        log.warning("[Dashboard] No running loop — component dropped")


def push_clear_sync() -> None:
    """Sync wrapper — schedules push_clear on the running event loop."""
    if _server is None:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_server.push_clear())
    except RuntimeError:
        pass
