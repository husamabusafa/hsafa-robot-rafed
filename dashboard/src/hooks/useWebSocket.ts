import { useEffect, useRef, useState, useCallback } from "react";
import type { DashboardMessage, DashboardLayout } from "../types";

const WS_URL = "ws://localhost:8765";
const RECONNECT_DELAY = 2000;

export function useWebSocket() {
  const [layout, setLayout] = useState<DashboardLayout | null>(null);
  const [status, setStatus] = useState<"idle" | "thinking" | "speaking" | "error" | "disconnected">("disconnected");
  const [statusText, setStatusText] = useState<string>("");
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setStatus("idle");
        console.log("[Dashboard] WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          const msg: DashboardMessage = JSON.parse(event.data);
          switch (msg.action) {
            case "render":
              if (msg.layout) {
                setLayout(msg.layout);
                setStatus("speaking");
              }
              break;
            case "init":
              if (msg.layout) {
                setLayout({ ...msg.layout, components: [] });
                setStatus("speaking");
              }
              break;
            case "add":
              if (msg.component) {
                setLayout((prev) => {
                  if (!prev) return prev;
                  return {
                    ...prev,
                    components: [...prev.components, msg.component!],
                  };
                });
              }
              break;
            case "clear":
              setLayout(null);
              setStatus("idle");
              break;
            case "status":
              if (msg.status) setStatus(msg.status);
              if (msg.text) setStatusText(msg.text);
              break;
          }
        } catch (e) {
          console.error("[Dashboard] Failed to parse message:", e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        setStatus("disconnected");
        console.log("[Dashboard] WebSocket disconnected, reconnecting...");
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      console.error("[Dashboard] WebSocket error:", e);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { layout, status, statusText, connected };
}
