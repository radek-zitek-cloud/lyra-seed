"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { AgentDetail } from "@/components/AgentDetail";
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

  // React to live events — refresh agent status on HITL and completion events
  useEffect(() => {
    if (liveEvents.length === 0) return;
    const latest = liveEvents[liveEvents.length - 1];
    const eventType = latest.event_type as string;

    // Merge into events list
    setEvents((prev) => {
      const ids = new Set(prev.map((e) => (e as Record<string, unknown>).id));
      const newEvents = liveEvents.filter((e) => !ids.has(e.id));
      return newEvents.length > 0 ? [...prev, ...newEvents] : prev;
    });

    // On HITL request or response, refresh agent to get updated status
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

    // Fire prompt in background — don't block UI
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
    // Agent will resume — refresh status
    fetchAgent(agentId).then(setAgent).catch(() => {});
  };

  if (!agent) {
    return <p style={{ color: "#333", fontSize: "12px" }}>Loading...</p>;
  }

  const toolEvents = (events as Record<string, unknown>[]).filter(
    (e) => e.event_type === "tool_call" || e.event_type === "tool_result",
  );

  // Show HITL panel when agent is waiting, based on live status
  const isWaitingHITL = (agent as Record<string, unknown>).status === "waiting_hitl";
  const hitlEvents = isWaitingHITL
    ? (events as Record<string, unknown>[]).filter(
        (e) => e.event_type === "hitl_request",
      )
    : [];
  // Only show the most recent HITL request
  const pendingHITL = hitlEvents.length > 0 ? [hitlEvents[hitlEvents.length - 1]] : [];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <a
          href="/"
          style={{
            fontSize: "11px",
            color: "#555",
            textDecoration: "none",
            border: "1px solid #222",
            borderRadius: "2px",
            padding: "4px 10px",
          }}
        >
          &larr; AGENTS
        </a>
        <ConnectionStatus state={connectionState} />
      </div>

      {sending && (
        <div
          style={{
            background: isWaitingHITL
              ? "rgba(255, 170, 0, 0.04)"
              : "rgba(0, 255, 65, 0.04)",
            border: `1px solid ${
              isWaitingHITL
                ? "rgba(255, 170, 0, 0.15)"
                : "rgba(0, 255, 65, 0.15)"
            }`,
            borderRadius: "4px",
            padding: "12px 16px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            animation: "pulse-glow 2s ease-in-out infinite",
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: isWaitingHITL ? "#ffaa00" : "#00ff41",
              animation: "blink 1s step-end infinite",
            }}
          />
          <span
            style={{
              fontSize: "12px",
              color: isWaitingHITL ? "#ffaa00" : "#00ff41",
              fontWeight: 700,
              letterSpacing: "1px",
            }}
          >
            {isWaitingHITL ? "WAITING FOR APPROVAL" : "AGENT RUNNING"}
          </span>
          <span style={{ fontSize: "11px", color: "#555" }}>
            {isWaitingHITL
              ? "Approve or deny the pending tool call below"
              : "Processing your request..."}
          </span>
        </div>
      )}

      {pendingHITL.length > 0 && (
        <HITLPanel
          pendingActions={pendingHITL as never}
          onRespond={handleHITLRespond}
        />
      )}

      <AgentDetail
        agent={agent as never}
        messages={messages as never}
        events={events as never}
      />

      <PromptInput onSubmit={handlePrompt} disabled={sending} />

      {toolEvents.length > 0 && (
        <ToolInspector toolEvents={toolEvents as never} />
      )}
    </div>
  );
}
