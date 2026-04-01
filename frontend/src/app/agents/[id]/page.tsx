"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    fetchAgent(agentId).then(setAgent).catch(() => {});
    fetchAgentEvents(agentId).then(setEvents).catch(() => {});
    fetchAgentConversations(agentId)
      .then((convos: { messages: { role: string; content: string }[] }[]) => {
        if (convos.length > 0) setMessages(convos[0].messages);
      })
      .catch(() => {});
  }, [agentId]);

  // Merge live events
  useEffect(() => {
    if (liveEvents.length > 0) {
      setEvents((prev) => [...prev, ...liveEvents.slice(prev.length)]);
    }
  }, [liveEvents]);

  const handlePrompt = async (message: string) => {
    setSending(true);
    try {
      await sendPrompt(agentId, message);
      const [a, evts, convos] = await Promise.all([
        fetchAgent(agentId),
        fetchAgentEvents(agentId),
        fetchAgentConversations(agentId),
      ]);
      setAgent(a);
      setEvents(evts);
      if (convos.length > 0) setMessages(convos[0].messages);
    } finally {
      setSending(false);
    }
  };

  const handleHITLRespond = async (
    id: string,
    approved: boolean,
    message?: string,
  ) => {
    await respondHITL(id, approved, message);
    const updated = await fetchAgent(agentId);
    setAgent(updated);
  };

  if (!agent) {
    return <p style={{ color: "#333", fontSize: "12px" }}>Loading...</p>;
  }

  const toolEvents = (events as Record<string, unknown>[]).filter(
    (e) => e.event_type === "tool_call" || e.event_type === "tool_result",
  );

  const hitlEvents = (events as Record<string, unknown>[]).filter(
    (e) =>
      e.event_type === "hitl_request" &&
      (agent as Record<string, unknown>).status === "waiting_hitl",
  );

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
            background: "rgba(0, 255, 65, 0.04)",
            border: "1px solid rgba(0, 255, 65, 0.15)",
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
              background: "#00ff41",
              animation: "blink 1s step-end infinite",
            }}
          />
          <span style={{ fontSize: "12px", color: "#00ff41", fontWeight: 700, letterSpacing: "1px" }}>
            AGENT RUNNING
          </span>
          <span style={{ fontSize: "11px", color: "#555" }}>
            Processing your request...
          </span>
        </div>
      )}

      <AgentDetail
        agent={agent as never}
        messages={messages as never}
        events={events as never}
      />

      <PromptInput onSubmit={handlePrompt} disabled={sending} />

      {hitlEvents.length > 0 && (
        <HITLPanel
          pendingActions={hitlEvents as never}
          onRespond={handleHITLRespond}
        />
      )}

      {toolEvents.length > 0 && (
        <ToolInspector toolEvents={toolEvents as never} />
      )}
    </div>
  );
}
