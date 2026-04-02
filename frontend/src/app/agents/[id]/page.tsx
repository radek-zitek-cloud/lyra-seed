"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { ConversationPanel, EventTimeline } from "@/components/AgentDetail";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { HITLPanel } from "@/components/HITLPanel";
import { PromptInput } from "@/components/PromptInput";
import { ToolInspector } from "@/components/ToolInspector";
import { useEventStream } from "@/hooks/useEventStream";
import {
  fetchAgent,
  fetchAgentConversations,
  fetchAgentEvents,
  respondHITL,
  sendPrompt,
} from "@/lib/api";

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  idle: { color: "#555", bg: "rgba(85,85,85,0.08)", border: "rgba(85,85,85,0.2)" },
  running: { color: "#00ff41", bg: "rgba(0,255,65,0.08)", border: "rgba(0,255,65,0.2)" },
  waiting_hitl: { color: "#ffaa00", bg: "rgba(255,170,0,0.08)", border: "rgba(255,170,0,0.2)" },
  completed: { color: "#00ff41", bg: "rgba(0,255,65,0.08)", border: "rgba(0,255,65,0.2)" },
  failed: { color: "#ff3333", bg: "rgba(255,51,51,0.08)", border: "rgba(255,51,51,0.2)" },
};
const DEFAULT_STATUS = { color: "#555", bg: "transparent", border: "#222" };

export default function AgentPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Record<string, unknown> | null>(null);
  const [messages, setMessages] = useState<
    { role: string; content: string; timestamp?: string }[]
  >([]);
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [sending, setSending] = useState(false);
  const { events: liveEvents, connectionState } = useEventStream(agentId);
  const promptInFlight = useRef(false);

  const refreshAll = async () => {
    const [a, evts, convos] = await Promise.all([
      fetchAgent(agentId),
      fetchAgentEvents(agentId),
      fetchAgentConversations(agentId),
    ]);
    setAgent(a);
    setEvents(evts);
    if (convos.length > 0) setMessages(convos[0].messages);
  };

  useEffect(() => {
    refreshAll().catch(() => {});
  }, [agentId]);

  useEffect(() => {
    if (liveEvents.length === 0) return;
    const latest = liveEvents[liveEvents.length - 1];
    const eventType = latest.event_type as string;

    setEvents((prev) => {
      const ids = new Set(prev.map((e) => (e as Record<string, unknown>).id));
      const newEvents = liveEvents.filter((e) => !ids.has(e.id));
      return newEvents.length > 0 ? [...prev, ...newEvents] : prev;
    });

    if (
      eventType === "hitl_request" ||
      eventType === "hitl_response" ||
      eventType === "error"
    ) {
      fetchAgent(agentId).then(setAgent).catch(() => {});
    }
  }, [liveEvents, agentId]);

  const handlePrompt = async (message: string) => {
    setSending(true);
    promptInFlight.current = true;
    // Show the human message immediately in the conversation
    setMessages((prev) => [...prev, { role: "human", content: message }]);

    sendPrompt(agentId, message)
      .then(() => refreshAll())
      .catch(() => {})
      .finally(() => {
        setSending(false);
        promptInFlight.current = false;
      });
  };

  const handleHITLRespond = async (
    id: string,
    approved: boolean,
    message?: string,
  ) => {
    await respondHITL(id, approved, message);
    fetchAgent(agentId).then(setAgent).catch(() => {});
  };

  if (!agent) {
    return <p style={{ color: "#333", fontSize: "12px" }}>Loading...</p>;
  }

  const toolEvents = (events as Record<string, unknown>[]).filter(
    (e) => e.event_type === "tool_call" || e.event_type === "tool_result",
  );

  const isWaitingHITL = (agent as Record<string, unknown>).status === "waiting_hitl";
  const hitlEvents = isWaitingHITL
    ? (events as Record<string, unknown>[]).filter(
        (e) => e.event_type === "hitl_request",
      )
    : [];
  const pendingHITL = hitlEvents.length > 0 ? [hitlEvents[hitlEvents.length - 1]] : [];

  const agentStatus = String((agent as Record<string, unknown>).status ?? "idle");
  const s = STATUS_STYLES[agentStatus] ?? DEFAULT_STATUS;
  const agentName = String((agent as Record<string, unknown>).name ?? "Agent");
  const agentConfig = (agent as Record<string, unknown>).config as Record<string, unknown> | undefined;
  const agentModel = String(agentConfig?.model ?? "default");

  return (
    <div>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "6px" }}>
        <span style={{ fontSize: "14px", fontWeight: 700, color: "#e0e0e0", letterSpacing: "1px" }}>
          {agentName}
        </span>
        <span style={{ fontSize: "11px", color: "#444" }}>{agentModel}</span>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 700,
            padding: "1px 8px",
            borderRadius: "2px",
            letterSpacing: "1px",
            color: s.color,
            background: s.bg,
            border: `1px solid ${s.border}`,
            animation:
              agentStatus === "running" || agentStatus === "waiting_hitl"
                ? "pulse-glow 1.5s ease-in-out infinite"
                : "none",
          }}
        >
          {agentStatus}
        </span>
        <span style={{ marginLeft: "auto" }}>
          <ConnectionStatus state={connectionState} />
        </span>
      </div>

      {/* Status banner */}
      {sending && (
        <div
          style={{
            background: isWaitingHITL ? "rgba(255,170,0,0.04)" : "rgba(0,255,65,0.04)",
            border: `1px solid ${isWaitingHITL ? "rgba(255,170,0,0.15)" : "rgba(0,255,65,0.15)"}`,
            borderRadius: "3px",
            padding: "4px 8px",
            marginBottom: "6px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            animation: "pulse-glow 2s ease-in-out infinite",
          }}
        >
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: isWaitingHITL ? "#ffaa00" : "#00ff41",
              animation: "blink 1s step-end infinite",
            }}
          />
          <span style={{ fontSize: "11px", color: isWaitingHITL ? "#ffaa00" : "#00ff41", fontWeight: 700, letterSpacing: "1px" }}>
            {isWaitingHITL ? "WAITING FOR APPROVAL" : "AGENT RUNNING"}
          </span>
        </div>
      )}

      {/* Main row: left = conversation + prompt + HITL, right = events */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <ConversationPanel messages={messages as never} />
          <PromptInput onSubmit={handlePrompt} disabled={sending} />
          {pendingHITL.length > 0 && (
            <HITLPanel
              pendingActions={pendingHITL as never}
              onRespond={handleHITLRespond}
            />
          )}
        </div>
        <EventTimeline events={events as never} />
      </div>

      {/* Tool inspector below */}
      {toolEvents.length > 0 && (
        <ToolInspector toolEvents={toolEvents as never} />
      )}
    </div>
  );
}
