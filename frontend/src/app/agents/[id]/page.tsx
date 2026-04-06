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
  reloadAgentConfig,
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
  const [streamingContent, setStreamingContent] = useState("");
  const { events: liveEvents, connectionState, connect, disconnect } = useEventStream(agentId);
  const promptInFlight = useRef(false);
  const streamingRef = useRef("");
  const processedCount = useRef(0);

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

    // Process all events since last render (handles batched SSE arrivals)
    const unprocessed = liveEvents.slice(processedCount.current);
    processedCount.current = liveEvents.length;
    if (unprocessed.length === 0) return;

    // Separate token events from control events
    const tokenEvents: typeof unprocessed = [];
    const controlEvents: typeof unprocessed = [];
    for (const evt of unprocessed) {
      if (evt.event_type === "llm_token") {
        tokenEvents.push(evt);
      } else {
        controlEvents.push(evt);
      }
    }

    // Accumulate streaming tokens
    if (tokenEvents.length > 0) {
      for (const evt of tokenEvents) {
        const token = (evt.payload as Record<string, unknown>)?.token;
        if (typeof token === "string") {
          streamingRef.current += token;
        }
      }
      setStreamingContent(streamingRef.current);
    }

    if (controlEvents.length === 0) return;

    // Add non-token events to timeline
    setEvents((prev) => {
      const ids = new Set(prev.map((e) => (e as Record<string, unknown>).id));
      const newEvents = controlEvents.filter(
        (e) => !ids.has(e.id),
      ) as unknown as Record<string, unknown>[];
      return newEvents.length > 0 ? [...prev, ...newEvents] : prev;
    });

    // Process side effects for each control event
    let shouldRefreshAgent = false;
    let shouldRefreshMessages = false;
    let shouldRefreshChildren = false;
    let shouldRefreshConversation = false;
    let shouldClearStreaming = false;

    for (const evt of controlEvents) {
      const et = evt.event_type as string;

      if (et === "llm_request" || et === "llm_response") {
        shouldClearStreaming = true;
      }

      if (et === "hitl_request" || et === "hitl_response" || et === "error" || et === "agent_complete") {
        shouldRefreshAgent = true;
      }

      if (et === "message_sent" || et === "message_received") {
        shouldRefreshMessages = true;
        shouldRefreshChildren = true;
      }

      if (et === "agent_spawn" || et === "agent_complete") {
        shouldRefreshChildren = true;
      }

      if (et === "agent_complete" || (et === "llm_response" && !promptInFlight.current)) {
        shouldRefreshConversation = true;
      }
    }

    if (shouldClearStreaming) {
      streamingRef.current = "";
      setStreamingContent("");
    }

    if (shouldRefreshAgent) {
      fetchAgent(agentId).then(setAgent).catch(() => {});
    }
    if (shouldRefreshMessages) {
      fetchAgentMessages(agentId).then(setAgentMessages).catch(() => {});
    }
    if (shouldRefreshChildren) {
      fetchAgentChildren(agentId).then(setChildren).catch(() => {});
    }
    if (shouldRefreshConversation) {
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const agentConfig = (agent as Record<string, unknown>).config as Record<string, any> | undefined;
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
        <button
          onClick={() => {
            reloadAgentConfig(agentId).then(() => refreshAll()).catch(() => {});
          }}
          style={{
            fontSize: "10px",
            fontWeight: 700,
            padding: "1px 8px",
            borderRadius: "2px",
            letterSpacing: "1px",
            color: "#8af",
            background: "rgba(136,170,255,0.08)",
            border: "1px solid rgba(136,170,255,0.2)",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          RELOAD CONFIG
        </button>
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
              {/* Core settings */}
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
                {agentConfig.hitl_timeout_seconds != null && (
                  <span><span style={{ color: "#555" }}>hitl_timeout </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.hitl_timeout_seconds)}s</span></span>
                )}
                {agentConfig.max_context_tokens != null && (
                  <span><span style={{ color: "#555" }}>ctx_tokens </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.max_context_tokens)}</span></span>
                )}
                {agentConfig.memory_top_k != null && (
                  <span><span style={{ color: "#555" }}>mem_k </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.memory_top_k)}</span></span>
                )}
                {agentConfig.max_subtasks != null && (
                  <span><span style={{ color: "#555" }}>max_subtasks </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.max_subtasks)}</span></span>
                )}
                {agentConfig.auto_extract != null && (
                  <span><span style={{ color: "#555" }}>auto_extract </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.auto_extract)}</span></span>
                )}
              </div>
              {/* Model overrides */}
              {(agentConfig.summary_model || agentConfig.extraction_model || agentConfig.orchestration_model) && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", fontSize: "11px" }}>
                  {!!agentConfig.summary_model && (
                    <span><span style={{ color: "#555" }}>summary_model </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.summary_model)}</span></span>
                  )}
                  {!!agentConfig.extraction_model && (
                    <span><span style={{ color: "#555" }}>extraction_model </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.extraction_model)}</span></span>
                  )}
                  {!!agentConfig.orchestration_model && (
                    <span><span style={{ color: "#555" }}>orchestration_model </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.orchestration_model)}</span></span>
                  )}
                </div>
              )}
              {/* Memory GC */}
              {(agentConfig.prune_threshold != null || agentConfig.prune_max_entries != null) && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", fontSize: "11px" }}>
                  {agentConfig.prune_threshold != null && (
                    <span><span style={{ color: "#555" }}>prune_threshold </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.prune_threshold)}</span></span>
                  )}
                  {agentConfig.prune_max_entries != null && (
                    <span><span style={{ color: "#555" }}>prune_max </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.prune_max_entries)}</span></span>
                  )}
                </div>
              )}
              {/* Retry config */}
              {agentConfig.retry && typeof agentConfig.retry === "object" && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", fontSize: "11px" }}>
                  {agentConfig.retry.max_retries != null && (
                    <span><span style={{ color: "#555" }}>retries </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.retry.max_retries)}</span></span>
                  )}
                  {agentConfig.retry.base_delay != null && (
                    <span><span style={{ color: "#555" }}>retry_delay </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.retry.base_delay)}s</span></span>
                  )}
                  {agentConfig.retry.timeout != null && (
                    <span><span style={{ color: "#555" }}>retry_timeout </span><span style={{ color: "#e0e0e0" }}>{String(agentConfig.retry.timeout)}s</span></span>
                  )}
                </div>
              )}
              {/* Tool & MCP access */}
              {Array.isArray(agentConfig.allowed_tools) && (agentConfig.allowed_tools as string[]).length > 0 && (
                <div style={{ fontSize: "11px" }}>
                  <span style={{ color: "#555" }}>allowed_tools </span>
                  <span style={{ color: "#aa66ff" }}>
                    {(agentConfig.allowed_tools as string[]).join(", ")}
                  </span>
                </div>
              )}
              {Array.isArray(agentConfig.allowed_mcp_servers) && (agentConfig.allowed_mcp_servers as string[]).length > 0 && (
                <div style={{ fontSize: "11px" }}>
                  <span style={{ color: "#555" }}>allowed_mcp </span>
                  <span style={{ color: "#00ccff" }}>
                    {(agentConfig.allowed_mcp_servers as string[]).join(", ")}
                  </span>
                </div>
              )}
              {/* Memory sharing */}
              {agentConfig.memory_sharing && typeof agentConfig.memory_sharing === "object" && Object.keys(agentConfig.memory_sharing as Record<string, unknown>).length > 0 && (
                <div style={{ fontSize: "11px" }}>
                  <span style={{ color: "#555" }}>memory_sharing </span>
                  <span style={{ color: "#00ff41" }}>
                    {Object.entries(agentConfig.memory_sharing as Record<string, string>).map(([k, v]) => `${k}:${v}`).join(", ")}
                  </span>
                </div>
              )}
              {/* System prompt */}
              {!!agentConfig.system_prompt && (
                <div style={{ fontSize: "11px" }}>
                  <div style={{ color: "#555", marginBottom: "2px" }}>system_prompt</div>
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
          <ConversationPanel messages={messages as never} streamingContent={streamingContent} />
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
