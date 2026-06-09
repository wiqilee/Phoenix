import { useEffect, useRef, useState } from "react";

export type AgentEvent = {
  type: string;
  payload: Record<string, unknown>;
  receivedAt: number;
};

const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://localhost:8080/ws";

/**
 * Subscribe to the live Phoenix agent activity stream via WebSocket.
 *
 * Returns the most recent events, the current connection status,
 * and a manual reconnect function.
 */
export function useAgentStream() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  const connect = () => {
    setStatus("connecting");

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("open");
    };

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setEvents((prev) => [
          ...prev.slice(-199),
          { ...parsed, receivedAt: Date.now() },
        ]);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setStatus("closed");
      reconnectTimerRef.current = window.setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  };

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reconnect = () => {
    wsRef.current?.close();
    connect();
  };

  const clear = () => setEvents([]);

  return { events, status, reconnect, clear };
}
