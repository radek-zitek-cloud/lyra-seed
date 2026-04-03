"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAgents, fetchAgentEvents } from "@/lib/api";
import type {
  GraphAgent,
  GraphMessage,
  GraphOrchestration,
  GraphSubtask,
} from "@/components/graph/graphUtils";

type ConnectionState = "connecting" | "connected" | "disconnected";

interface EventItem {
  agent_id: string;
  event_type: string;
  module: string;
  payload: Record<string, unknown>;
}

export function useGraphData() {
  const [agents, setAgents] = useState<GraphAgent[]>([]);
  const [messages, setMessages] = useState<GraphMessage[]>([]);
  const [orchestrations, setOrchestrations] = useState<GraphOrchestration[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");

  const sourceRef = useRef<EventSource | null>(null);
  const manualDisconnect = useRef(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const agentRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      const data = await fetchAgents();
      setAgents(data);
    } catch {
      // Silently ignore — will retry on next SSE event
    }
  }, []);

  const loadOrchestrations = useCallback(async (agentList: GraphAgent[]) => {
    const results: GraphOrchestration[] = [];
    for (const agent of agentList) {
      try {
        const events = await fetchAgentEvents(agent.id, {
          module: "orchestration.orchestrate",
        });
        // Find the most recent orchestrate TOOL_CALL event (has plan with subtasks)
        for (const evt of events) {
          if (
            evt.event_type === "tool_call" &&
            evt.payload?.subtask_count
          ) {
            // Get subtask details from strategy events
            const strategyEvents = await fetchAgentEvents(agent.id, {
              module: "orchestration.strategy",
            });
            const subtasks: GraphSubtask[] = [];
            const seen = new Set<string>();
            for (const se of strategyEvents) {
              const stId = se.payload?.subtask_id as string;
              if (!stId || seen.has(stId)) {
                // Update status if we already have this subtask (result event)
                if (stId && seen.has(stId) && se.event_type === "tool_result") {
                  const existing = subtasks.find((s) => s.id === stId);
                  if (existing) {
                    existing.status = (se.payload?.status as string) ?? existing.status;
                  }
                }
                continue;
              }
              seen.add(stId);
              subtasks.push({
                id: stId,
                description: (se.payload?.description as string) ?? "",
                status: (se.payload?.status as string) ?? "pending",
                dependencies: (se.payload?.dependencies as number[]) ?? [],
              });
            }

            // Check if synthesis completed
            const resultEvents = events.filter(
              (e: Record<string, unknown>) =>
                e.event_type === "tool_result" &&
                (e.payload as Record<string, unknown>)?.plan_id === evt.payload?.plan_id,
            );
            const synthesized = resultEvents.length > 0;

            // Update subtask statuses from result events
            for (const se of strategyEvents) {
              if (se.event_type === "tool_result") {
                const st = subtasks.find((s) => s.id === se.payload?.subtask_id);
                if (st) st.status = (se.payload?.status as string) ?? st.status;
              }
            }

            results.push({
              agent_id: agent.id,
              plan_id: evt.payload?.plan_id as string,
              strategy: (evt.payload?.strategy as string) ?? "sequential",
              subtasks,
              synthesized,
            });
            break; // Use most recent orchestration only
          }
        }
      } catch {
        // Agent may not have orchestration events
      }
    }
    setOrchestrations(results);
  }, []);

  const refresh = useCallback(async () => {
    const data = await fetchAgents();
    setAgents(data);
    await loadOrchestrations(data);
  }, [loadOrchestrations]);

  // SSE connection
  const connect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    manualDisconnect.current = false;

    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const url = `${base}/events/stream`;

    setConnectionState("connecting");
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setConnectionState("connected");

    source.onmessage = (raw) => {
      const evt: EventItem = JSON.parse(raw.data);

      // Update graph based on event type — any event that may change agent status
      // Debounced to avoid spamming fetches on rapid events (e.g. multiple llm_request per turn)
      if (
        evt.event_type === "agent_spawn" ||
        evt.event_type === "agent_complete" ||
        evt.event_type === "error" ||
        evt.event_type === "llm_request" ||
        evt.event_type === "hitl_request" ||
        evt.event_type === "hitl_response"
      ) {
        if (agentRefreshTimer.current) clearTimeout(agentRefreshTimer.current);
        agentRefreshTimer.current = setTimeout(() => loadAgents(), 200);
      }

      if (evt.event_type === "message_sent") {
        const payload = evt.payload;
        setMessages((prev) => [
          ...prev,
          {
            id: (payload.message_id as string) ?? "",
            from_agent_id: evt.agent_id,
            to_agent_id: (payload.to_agent_id as string) ?? "",
            content: (payload.content_preview as string) ?? "",
            message_type: (payload.message_type as string) ?? "",
            timestamp: new Date().toISOString(),
          },
        ]);
      }

      if (evt.module?.startsWith("orchestration.")) {
        // Re-fetch orchestration data for this agent
        loadAgents().then(() => {
          fetchAgents().then((data) => loadOrchestrations(data));
        });
      }
    };

    source.onerror = () => {
      source.close();
      sourceRef.current = null;
      setConnectionState("disconnected");
      if (!manualDisconnect.current) {
        reconnectTimer.current = setTimeout(connect, 3000);
      }
    };
  }, [loadAgents, loadOrchestrations]);

  const disconnect = useCallback(() => {
    manualDisconnect.current = true;
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (agentRefreshTimer.current) {
      clearTimeout(agentRefreshTimer.current);
      agentRefreshTimer.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setConnectionState("disconnected");
  }, []);

  // Initial load + SSE connect
  useEffect(() => {
    refresh();
    connect();

    // Re-render periodically so short time range filters stay current
    const refreshInterval = setInterval(() => {
      setMessages((prev) => [...prev]);
    }, 5_000);

    return () => {
      manualDisconnect.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (agentRefreshTimer.current) clearTimeout(agentRefreshTimer.current);
      clearInterval(refreshInterval);
      sourceRef.current?.close();
    };
  }, [refresh, connect]);

  return { agents, messages, orchestrations, connectionState, connect, disconnect, refresh };
}
