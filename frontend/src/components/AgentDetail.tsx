"use client";

import { useEffect, useRef, useState } from "react";

interface Agent {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface Message {
  role: string;
  content: string;
  timestamp?: string;
  tool_calls?: unknown[];
}

interface EventItem {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: Record<string, unknown>;
  duration_ms?: number | null;
  parent_event_id?: string | null;
}

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  idle: { color: "#555", bg: "rgba(85,85,85,0.08)", border: "rgba(85,85,85,0.2)" },
  running: { color: "#00ff41", bg: "rgba(0,255,65,0.08)", border: "rgba(0,255,65,0.2)" },
  waiting_hitl: { color: "#ffaa00", bg: "rgba(255,170,0,0.08)", border: "rgba(255,170,0,0.2)" },
  completed: { color: "#00ff41", bg: "rgba(0,255,65,0.08)", border: "rgba(0,255,65,0.2)" },
  failed: { color: "#ff3333", bg: "rgba(255,51,51,0.08)", border: "rgba(255,51,51,0.2)" },
};

const EVENT_COLORS: Record<string, string> = {
  llm_request: "#6688ff",
  llm_response: "#4466dd",
  tool_call: "#aa66ff",
  tool_result: "#8844cc",
  memory_read: "#00ff41",
  memory_write: "#00cc33",
  hitl_request: "#ffaa00",
  hitl_response: "#cc8800",
  error: "#ff3333",
  agent_spawn: "#00ccff",
  agent_complete: "#0099cc",
};

const DEFAULT_STATUS = { color: "#555", bg: "transparent", border: "#222" };

export function AgentDetail({
  agent,
  messages,
  events,
}: {
  agent: Agent;
  messages: Message[];
  events: EventItem[];
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const s = STATUS_STYLES[agent.status] ?? DEFAULT_STATUS;
  const convoEndRef = useRef<HTMLDivElement>(null);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    convoEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [events]);

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingBottom: "16px",
          marginBottom: "24px",
          borderBottom: "1px solid #1a1a1a",
        }}
      >
        <div>
          <h1 style={{ fontSize: "18px", fontWeight: 700, color: "#e0e0e0", letterSpacing: "2px" }}>
            {agent.name}
          </h1>
          <div style={{ fontSize: "12px", color: "#555", marginTop: "4px" }}>
            MODEL: {String(agent.config?.model ?? "default")}
          </div>
        </div>
        <span
          style={{
            fontSize: "12px",
            fontWeight: 700,
            padding: "2px 10px",
            borderRadius: "2px",
            letterSpacing: "1px",
            color: s.color,
            background: s.bg,
            border: `1px solid ${s.border}`,
            animation:
              agent.status === "running" || agent.status === "waiting_hitl"
                ? "pulse-glow 1.5s ease-in-out infinite"
                : "none",
          }}
        >
          {agent.status}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        {/* Conversation Panel */}
        <div
          style={{
            background: "#111",
            border: "1px solid #1a1a1a",
            borderRadius: "4px",
            padding: "20px",
          }}
        >
          <h2
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "#555",
              letterSpacing: "1px",
              marginBottom: "16px",
            }}
          >
            CONVERSATION
          </h2>
          <div style={{ maxHeight: "400px", overflowY: "auto" }}>
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  padding: "10px 12px",
                  marginBottom: "8px",
                  borderLeft: `3px solid ${
                    msg.role === "human"
                      ? "#6688ff"
                      : msg.role === "assistant"
                        ? "#00ff41"
                        : "#555"
                  }`,
                  background: "#0a0a0a",
                  borderRadius: "0 2px 2px 0",
                }}
              >
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    color: "#555",
                    letterSpacing: "1px",
                    marginBottom: "6px",
                    textTransform: "uppercase",
                  }}
                >
                  {msg.role}
                </div>
                <div style={{ color: "#b0b0b0", fontSize: "13px", whiteSpace: "pre-wrap" }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {messages.length === 0 && (
              <div style={{ color: "#333", textAlign: "center", padding: "16px", fontSize: "12px" }}>
                No messages yet.
              </div>
            )}
            <div ref={convoEndRef} />
          </div>
        </div>

        {/* Event Timeline */}
        <div
          style={{
            background: "#111",
            border: "1px solid #1a1a1a",
            borderRadius: "4px",
            padding: "20px",
          }}
        >
          <h2
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "#555",
              letterSpacing: "1px",
              marginBottom: "16px",
            }}
          >
            EVENTS
          </h2>
          <div style={{ maxHeight: "400px", overflowY: "auto" }}>
            {events.map((evt) => {
              const color = EVENT_COLORS[evt.event_type] ?? "#555";
              return (
                <div key={evt.id} style={{ borderLeft: `3px solid ${color}`, marginBottom: "4px" }}>
                  <button
                    onClick={() => toggle(evt.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      width: "100%",
                      padding: "6px 10px",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontFamily: "inherit",
                      fontSize: "12px",
                      color: "#b0b0b0",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#0a0a0a")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ color: "#444", fontSize: "10px" }}>
                        {expanded.has(evt.id) ? "\u25BC" : "\u25B6"}
                      </span>
                      <span style={{ color, fontWeight: 700, letterSpacing: "0.5px" }}>
                        {evt.event_type}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {evt.duration_ms != null && (
                        <span style={{ color: "#444", fontSize: "11px" }}>{evt.duration_ms}ms</span>
                      )}
                      <span style={{ color: "#333", fontSize: "11px" }}>{evt.module}</span>
                    </div>
                  </button>
                  {expanded.has(evt.id) && (
                    <div style={{ padding: "0 10px 8px" }}>
                      <pre
                        style={{
                          fontSize: "11px",
                          color: "#555",
                          background: "#0a0a0a",
                          border: "1px solid #1a1a1a",
                          borderRadius: "2px",
                          padding: "10px",
                          overflowX: "auto",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {JSON.stringify(evt.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
            {events.length === 0 && (
              <div style={{ color: "#333", textAlign: "center", padding: "16px", fontSize: "12px" }}>
                No events yet.
              </div>
            )}
            <div ref={eventsEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
