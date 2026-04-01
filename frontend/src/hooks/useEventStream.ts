"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type ConnectionState = "connecting" | "connected" | "disconnected";

interface EventItem {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: Record<string, unknown>;
  duration_ms?: number | null;
}

export function useEventStream(agentId?: string) {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const wsBase = (
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    ).replace(/^http/, "ws");
    const url = agentId
      ? `${wsBase}/agents/${agentId}/events/stream`
      : `${wsBase}/events/stream`;

    setConnectionState("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnectionState("connected");

    ws.onmessage = (msg) => {
      const event: EventItem = JSON.parse(msg.data);
      setEvents((prev) => [...prev, event]);
    };

    ws.onclose = () => {
      setConnectionState("disconnected");
      // Reconnect after 3 seconds
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [agentId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { events, connectionState };
}
