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
  const sourceRef = useRef<EventSource | null>(null);
  const manualDisconnect = useRef(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    manualDisconnect.current = false;

    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const url = agentId
      ? `${base}/agents/${agentId}/events/stream`
      : `${base}/events/stream`;

    setConnectionState("connecting");
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setConnectionState("connected");

    source.onmessage = (msg) => {
      const event: EventItem = JSON.parse(msg.data);
      setEvents((prev) => [...prev, event]);
    };

    source.onerror = () => {
      source.close();
      sourceRef.current = null;
      setConnectionState("disconnected");
      // Only auto-reconnect if not manually disconnected
      if (!manualDisconnect.current) {
        reconnectTimer.current = setTimeout(connect, 3000);
      }
    };
  }, [agentId]);

  const disconnect = useCallback(() => {
    manualDisconnect.current = true;
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setConnectionState("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => {
      manualDisconnect.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      sourceRef.current?.close();
    };
  }, [connect]);

  return { events, connectionState, connect, disconnect };
}
