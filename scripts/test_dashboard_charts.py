#!/usr/bin/env python3
"""Test script — pushes sample charts to the dashboard via WebSocket.

Run: python scripts/test_dashboard_charts.py
Then open http://localhost:5173 in the browser.
"""
import asyncio
import json
import logging

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("test_dashboard")

HOST = "localhost"
PORT = 8765


async def test_charts():
    server = await websockets.serve(handler, HOST, PORT)
    log.info("WebSocket test server on ws://%s:%d — open http://localhost:5173", HOST, PORT)
    log.info("Press Ctrl+C to stop.")
    await asyncio.Future()  # run forever


clients = set()


async def handler(ws):
    clients.add(ws)
    log.info("Client connected (%d total)", len(clients))
    try:
        await ws.wait_closed()
    finally:
        clients.discard(ws)
        log.info("Client disconnected (%d total)", len(clients))


async def broadcast(msg):
    if not clients:
        return
    payload = json.dumps(msg, ensure_ascii=False)
    await asyncio.gather(*[c.send(payload) for c in clients], return_exceptions=True)


async def push_test_data():
    """Push a full dashboard with all chart types."""
    await asyncio.sleep(1)  # wait for client

    # Init dashboard
    await broadcast({
        "action": "init",
        "layout": {
            "title": "اختبار الرسوم البيانية",
            "subtitle": "Test — All Chart Types",
            "columns": 3,
            "components": [],
        },
    })
    log.info("Pushed init")
    await asyncio.sleep(0.5)

    # KPI
    await broadcast({"action": "add", "component": {
        "type": "kpi", "title": "إجمالي الحافلات", "value": 25512,
        "icon": "bus", "color": "blue", "span": 1,
    }})
    log.info("Pushed KPI")
    await asyncio.sleep(0.5)

    # Donut
    await broadcast({"action": "add", "component": {
        "type": "donut", "title": "تغطية GPS", "span": 2,
        "data": [
            {"label": "مع GPS", "value": 19338},
            {"label": "بدون GPS", "value": 6174},
        ],
        "centerLabel": "GPS", "centerValue": "75.8%",
    }})
    log.info("Pushed Donut")
    await asyncio.sleep(0.5)

    # Bar
    await broadcast({"action": "add", "component": {
        "type": "bar", "title": "المؤشرات التشغيلية", "span": 2,
        "data": [
            {"label": "العقود", "value": 108},
            {"label": "الحوادث", "value": 561},
            {"label": "الشكاوى", "value": 23},
            {"label": "الفجوة", "value": 45},
        ],
        "horizontal": False,
    }})
    log.info("Pushed Bar")
    await asyncio.sleep(0.5)

    # Pie
    await broadcast({"action": "add", "component": {
        "type": "pie", "title": "توزيع الحافلات", "span": 1,
        "data": [
            {"label": "صغيرة", "value": 12000},
            {"label": "متوسطة", "value": 8000},
            {"label": "كبيرة", "value": 5512},
        ],
    }})
    log.info("Pushed Pie")
    await asyncio.sleep(0.5)

    # Line
    await broadcast({"action": "add", "component": {
        "type": "line", "title": "الحوادث الشهرية", "span": 2,
        "data": [
            {"label": "يناير", "value": 45},
            {"label": "فبراير", "value": 52},
            {"label": "مارس", "value": 38},
            {"label": "أبريل", "value": 61},
            {"label": "مايو", "value": 48},
            {"label": "يونيو", "value": 561},
        ],
    }})
    log.info("Pushed Line")
    await asyncio.sleep(0.5)

    # Area
    await broadcast({"action": "add", "component": {
        "type": "area", "title": "حجم النقل الشهري", "span": 2,
        "stacked": False,
        "series": [
            {"name": "الرياض", "color": "#3377ff", "data": [
                {"label": "يناير", "value": 1200},
                {"label": "فبراير", "value": 1350},
                {"label": "مارس", "value": 1100},
                {"label": "أبريل", "value": 1500},
                {"label": "مايو", "value": 1400},
            ]},
            {"name": "جدة", "color": "#10b981", "data": [
                {"label": "يناير", "value": 800},
                {"label": "فبراير", "value": 950},
                {"label": "مارس", "value": 850},
                {"label": "أبريل", "value": 1000},
                {"label": "مايو", "value": 900},
            ]},
        ],
    }})
    log.info("Pushed Area")
    await asyncio.sleep(0.5)

    # Radar
    await broadcast({"action": "add", "component": {
        "type": "radar", "title": "أداء المشغلين", "span": 1,
        "max": 100,
        "series": [
            {"name": "المشغل أ", "color": "#3377ff", "data": [
                {"label": "الأمان", "value": 85},
                {"label": "الالتزام", "value": 92},
                {"label": "التغطية", "value": 78},
                {"label": "الكفاءة", "value": 88},
                {"label": "الرضا", "value": 75},
            ]},
            {"name": "المشغل ب", "color": "#f59e0b", "data": [
                {"label": "الأمان", "value": 70},
                {"label": "الالتزام", "value": 80},
                {"label": "التغطية", "value": 95},
                {"label": "الكفاءة", "value": 72},
                {"label": "الرضا", "value": 82},
            ]},
        ],
    }})
    log.info("Pushed Radar")
    await asyncio.sleep(0.5)

    # Scatter
    await broadcast({"action": "add", "component": {
        "type": "scatter", "title": "العمر مقابل الصيانة", "span": 2,
        "xLabel": "عمر الحافلة (سنوات)",
        "yLabel": "تكلفة الصيانة (ريال)",
        "series": [
            {"name": "الرياض", "color": "#3377ff", "data": [
                {"x": 2, "y": 5000, "label": "حافلة 1"},
                {"x": 5, "y": 12000, "label": "حافلة 2"},
                {"x": 8, "y": 25000, "label": "حافلة 3"},
                {"x": 10, "y": 35000, "label": "حافلة 4"},
                {"x": 12, "y": 45000, "label": "حافلة 5"},
            ]},
            {"name": "جدة", "color": "#10b981", "data": [
                {"x": 1, "y": 3000, "label": "حافلة 6"},
                {"x": 4, "y": 8000, "label": "حافلة 7"},
                {"x": 7, "y": 18000, "label": "حافلة 8"},
                {"x": 9, "y": 30000, "label": "حافلة 9"},
                {"x": 11, "y": 40000, "label": "حافلة 10"},
            ]},
        ],
    }})
    log.info("Pushed Scatter")
    log.info("All charts pushed! Check the browser.")


async def main():
    # Start WebSocket server
    server = await websockets.serve(handler, HOST, PORT)
    log.info("WebSocket test server on ws://%s:%d", HOST, PORT)
    log.info("Open http://localhost:5173 in the browser to see charts.")
    log.info("Press Ctrl+C to stop.")

    # Push test data in background
    asyncio.create_task(push_test_data())

    # Keep running
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
