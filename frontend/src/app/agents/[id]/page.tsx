"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { ConversationPanel, EventTimeline } from "@/components/AgentDetail";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { HITLPanel } from "@/components/HITLPanel";
import { MessagePanel } from "@/components/MessagePanel";
import { PromptInput } from "@/components/PromptInput";
import { useEventStream } from "@/hooks/useEventStream";
import {
  fetchAgent,
  fetchAgentChildren,
  fetchAgentConversations,
  fetchAgentCost,
  fetchAgentEvents,
  fetchAgentMessages,
  resetAgent,
  respondHITL,
  sendAgentMessage,
  sendPrompt,
} from "@/lib/api";

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  idle: { color: "#555", bg: "rgba(85,85,85,0.08)", border: "rgba(85,85,85,0.2)" },
  running: { color: "#00ff41", bg: "rgba(0,255,65,0.08)", border: "rgba(0,255,65,0.2)" },
  waiting_hitl: { color: "#ffaa00", bg: "rgba(255,170,0,0.08)", border: "rgba(255,170,0,0.2)" },
  completed: { color: "#6688ff", bg: "rgba(102,136,255,0.08)", border: "rgba(102,136,255,0.2)" },
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
  const [cost, setCost] = useState<{ total_cost_usd: number; total_prompt_tokens: number; total_completion_tokens: number } | null>(null);
  const [children, setChildren] = useState<{ id: string; name: string; status: string }[]>([]);
  const [agentMessages, setAgentMessages] = useState<Record<string, unknown>[]>([]);
  const [sending, setSending] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const { events: liveEvents, connectionState, connect, disconnect } = useEventStream(agentId);
  const promptInFlight = useRef(false);

  const refreshAll = async () => {
    const [a, evts, convos, c, ch, msgs] = await Promise.all([
      fetchAgent(agentId),
      fetchAgentEvents(agentId),
      fetchAgentConversations(agentId),
      fetchAgentCost(agentId),
      fetchAgentChildren(agentId).catch(() => []),
      fetchAgentMessages(agentId).catch(() => []),
    ]);
    setAgent(a);
    setEvents(evts);
    setCost(c);
    setChildren(ch);
    setAgentMessages(msgs);
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
      eventType === "error" ||
      eventType === "agent_complete"
    ) {
      fetchAgent(agentId).then(setAgent).catch(() => {});
    }

    if (
      eventType === "message_sent" ||
      eventType === "message_received"
    ) {
      fetchAgentMessages(agentId).then(setAgentMessages).catch(() => {});
      // Child status may have changed (sent task → running, got result → idle)
      fetchAgentChildren(agentId).then(setChildren).catch(() => {});
    }

    if (eventType === "agent_spawn" || eventType === "agent_complete") {
      fetchAgentChildren(agentId).then(setChildren).catch(() => {});
    }

    // Refresh conversation when agent completes a turn
    // Skip mid-turn refreshes while prompt is in flight to prevent
    // the optimistic human message from disappearing
    if (
      eventType === "agent_complete" ||
      (eventType === "llm_response" && !promptInFlight.current)
    ) {
      fetchAgentConversations(agentId)
        .then((convos: { messages: { role: string; content: string }[] }[]) => {
          if (convos.length > 0) setMessages(convos[0].messages);
        })
        .catch(() => {});
    }
  }, [liveEvents, agentId]);

  const handlePrompt = async (message: string) => {
    setSending(true);
    promptInFlight.current = true;
    setMessages((prev) => [...prev, { role: "human", content: message }]);

    sendPrompt(agentId, message)
      .then(() => refreshAll())
      .catch(() => {})
      .finally(() => {
        setSending(false);
        promptInFlight.current = false;
      });
  };

  const handleSendMessage = async (content: string, messageType: string) => {
    await sendAgentMessage(agentId, content, messageType);
    const msgs = await fetchAgentMessages(agentId);
    setAgentMessages(msgs);
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
  const parentId = (agent as Record<string, unknown>).parent_agent_id as string | null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px", flexShrink: 0 }}>
        {parentId && (
          <a
            href={`/agents/${parentId}`}
            style={{
              fontSize: "10px",
              color: "#555",
              textDecoration: "none",
              border: "1px solid #222",
              borderRadius: "2px",
              padding: "1px 6px",
            }}
          >
            &larr; PARENT
          </a>
        )}
        <span style={{ fontSize: "14px", fontWeight: 700, color: "#e0e0e0", letterSpacing: "1px" }}>
          {agentName}
        </span>
        <span style={{ fontSize: "11px", color: "#888" }}>{agentModel}</span>
        {cost && cost.total_cost_usd > 0 && (
          <span style={{ fontSize: "11px", color: "#cc9933" }}>
            ${cost.total_cost_usd.toFixed(4)}
          </span>
        )}
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
        {(agentStatus === "failed" || agentStatus === "completed") && (
          <button
            onClick={() => {
              resetAgent(agentId).then(() => refreshAll()).catch(() => {});
            }}
            style={{
              fontSize: "10px",
              fontWeight: 700,
              padding: "1px 8px",
              borderRadius: "2px",
              letterSpacing: "1px",
              color: "#e8a",
              background: "rgba(255,200,100,0.08)",
              border: "1px solid rgba(255,200,100,0.2)",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            RESET
          </button>
        )}
        {sending && (
          <>
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
              {isWaitingHITL ? "AWAITING APPROVAL" : "RUNNING"}
            </span>
          </>
        )}
        <span style={{ marginLeft: "auto" }}>
          <ConnectionStatus state={connectionState} onConnect={connect} onDisconnect={disconnect} />
        </span>
      </div>

      {/* Config panel (collapsible) */}
      {agentConfig && (
        <div style={{ flexShrink: 0, marginBottom: showConfig ? "6px" : 0 }}>
          <button
            onClick={() => setShowConfig((v) => !v)}
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#555",
              letterSpacing: "1px",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "2px 0",
              fontFamily: "inherit",
            }}
          >
            {showConfig ? "\u25BC" : "\u25B6"} CONFIG
          </button>
          {showConfig && (
            <div style={{
              background: "#111",
              border: "1px solid #1a1a1a",
              borderRadius: "3px",
              padding: "6px",
              marginTop: "2px",
              display: "flex",
              flexDirection: "column",
              gap: "6px",
            }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", fontSize: "11px" }}>
                {!!agentConfig.model && (
                  <span><span style={{ color: "#555" }}>model </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.model)}</span></span>
                )}
                {agentConfig.temperature != null && (
                  <span><span style={{ color: "#555" }}>temp </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.temperature)}</span></span>
                )}
                {agentConfig.max_iterations != null && (
                  <span><span style={{ color: "#555" }}>max_iter </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.max_iterations)}</span></span>
                )}
                {!!agentConfig.hitl_policy && (
                  <span><span style={{ color: "#555" }}>hitl </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.hitl_policy)}</span></span>
                )}
                {agentConfig.max_context_tokens != null && (
                  <span><span style={{ color: "#555" }}>ctx_tokens </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.max_context_tokens)}</span></span>
                )}
                {agentConfig.memory_top_k != null && (
                  <span><span style={{ color: "#555" }}>mem_k </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.memory_top_k)}</span></span>
                )}
              </div>
              {Array.isArray(agentConfig.allowed_tools) && (agentConfig.allowed_tools as string[]).length > 0 && (
                <div style={{ fontSize: "11px" }}>
                  <span style={{ color: "#555" }}>tools </span>
                  <span style={{ color: "#aa66ff" }}>
                    {(agentConfig.allowed_tools as string[]).join(", ")}
                  </span>
                </div>
              )}
              {!!agentConfig.system_prompt && (
                <div style={{ fontSize: "11px" }}>
                  <div style={{ color: "#555", marginBottom: "2px" }}>system prompt</div>
                  <pre style={{
                    color: "#b0b0b0",
                    background: "#0a0a0a",
                    border: "1px solid #1a1a1a",
                    borderRadius: "2px",
                    padding: "4px",
                    fontSize: "10px",
                    whiteSpace: "pre-wrap",
                    maxHeight: "200px",
                    overflowY: "auto",
                    margin: 0,
                  }}>
                    {String(agentConfig.system_prompt)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Child agents */}
      {children.length > 0 && (
        <div style={{
          background: "#111",
          border: "1px solid #1a1a1a",
          borderRadius: "3px",
          padding: "6px",
          marginBottom: "6px",
          flexShrink: 0,
        }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#888", letterSpacing: "1px", marginBottom: "4px" }}>
            SUB-AGENTS
          </div>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {children.map((ch) => {
              const chStatus = STATUS_STYLES[ch.status] ?? DEFAULT_STATUS;
              return (
                <a
                  key={ch.id}
                  href={`/agents/${ch.id}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "3px 8px",
                    background: "#0a0a0a",
                    border: "1px solid #222",
                    borderRadius: "2px",
                    textDecoration: "none",
                    fontSize: "11px",
                  }}
                >
                  <span style={{ color: "#e0e0e0", fontWeight: 700 }}>{ch.name}</span>
                  <span style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: chStatus.color,
                    letterSpacing: "0.5px",
                    animation: ch.status === "running" ? "pulse-glow 1.5s ease-in-out infinite" : "none",
                  }}>
                    {ch.status}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {/* Two-column layout filling viewport */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", flex: 1, minHeight: 0 }}>
        {/* Left column: conversation + prompt + HITL */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", minHeight: 0 }}>
          <ConversationPanel messages={messages as never} />
          <PromptInput onSubmit={handlePrompt} disabled={sending} />
          {pendingHITL.length > 0 && (
            <HITLPanel
              pendingActions={pendingHITL as never}
              onRespond={handleHITLRespond}
            />
          )}
          <MessagePanel
            messages={agentMessages as never}
            currentAgentId={agentId}
            onSend={handleSendMessage}
          />
        </div>

        {/* Right column: event timeline */}
        <EventTimeline events={events as never} />
      </div>
    </div>
  );
}
