"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function fmtTime(ts?: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toISOString().slice(11, 19);
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

const ROLE_COLORS: Record<string, string> = {
  human: "#6688ff",
  assistant: "#00ff41",
  system: "#555",
  tool_result: "#8844cc",
};

/** Extract key info from event payload for inline display. */
function eventSummary(evt: EventItem): string {
  const p = evt.payload;
  switch (evt.event_type) {
    case "llm_request":
      if (p.model) return `model=${p.model} msgs=${p.message_count ?? "?"}`;
      if (p.iteration) return `iter=${p.iteration} msgs=${p.message_count ?? "?"}`;
      return "";
    case "llm_response":
      if (p.usage && typeof p.usage === "object") {
        const u = p.usage as Record<string, unknown>;
        const inTok = u.prompt_tokens ?? u.input_tokens ?? "?";
        const outTok = u.completion_tokens ?? u.output_tokens ?? "?";
        return `in=${inTok} out=${outTok}`;
      }
      if (p.tool_call_count) return `tools=${p.tool_call_count}`;
      return "";
    case "tool_call":
      return (p.tool_name ?? p.tool) ? String(p.tool_name ?? p.tool) : "";
    case "tool_result": {
      const name = (p.tool_name ?? p.tool) ? String(p.tool_name ?? p.tool) : "";
      const ok = p.success !== undefined ? (p.success ? "ok" : "fail") : "";
      const dur = p.duration_ms ? `${p.duration_ms}ms` : "";
      return [name, ok, dur].filter(Boolean).join(" ");
    }
    case "memory_read":
      if (p.query) return `"${String(p.query).slice(0, 40)}"`;
      if (p.results_count !== undefined) return `${p.results_count} results`;
      return "";
    case "memory_write":
      return p.memory_type
        ? `${p.memory_type} ${p.content_preview ? String(p.content_preview).slice(0, 30) + "…" : ""}`
        : "";
    case "error":
      return p.error ? String(p.error).slice(0, 50) : "";
    case "hitl_request":
      return (p.tool_name ?? p.tool) ? `tool=${p.tool_name ?? p.tool}` : "";
    case "hitl_response":
      return p.approved !== undefined ? (p.approved ? "approved" : "denied") : "";
    default:
      return "";
  }
}

function isNearBottom(el: HTMLElement, threshold = 30): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

/* ── Conversation Panel ─────────────────────────────── */

export function ConversationPanel({ messages }: { messages: Message[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) wasAtBottom.current = isNearBottom(el);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div style={{ background: "#111", border: "1px solid #1a1a1a", borderRadius: "3px", padding: "6px" }}>
      <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#555", letterSpacing: "1px", marginBottom: "4px" }}>
        CONVERSATION
      </h2>
      <div ref={scrollRef} onScroll={handleScroll} style={{ maxHeight: "500px", overflowY: "auto" }}>
        {messages.map((msg, i) => {
          const roleColor = ROLE_COLORS[msg.role] ?? "#555";
          return (
            <div
              key={i}
              style={{
                padding: "2px 4px",
                marginBottom: "1px",
                borderLeft: `2px solid ${roleColor}`,
                background: "#0a0a0a",
                fontSize: "12px",
                lineHeight: "1.4",
              }}
            >
              <span style={{ color: roleColor, fontWeight: 700, fontSize: "10px", letterSpacing: "0.5px", textTransform: "uppercase", marginRight: "6px" }}>
                {msg.role}:
              </span>
              <span style={{ color: "#b0b0b0", whiteSpace: msg.role === "tool_result" ? "nowrap" : "pre-wrap", overflow: msg.role === "tool_result" ? "hidden" : undefined, textOverflow: msg.role === "tool_result" ? "ellipsis" : undefined }}>
                {msg.role === "tool_result" ? msg.content.slice(0, 80) + (msg.content.length > 80 ? "…" : "") : msg.content}
              </span>
              {msg.timestamp && (
                <span style={{ color: "#333", fontSize: "10px", marginLeft: "6px" }}>{fmtTime(msg.timestamp)}</span>
              )}
            </div>
          );
        })}
        {messages.length === 0 && (
          <div style={{ color: "#333", textAlign: "center", padding: "8px", fontSize: "11px" }}>
            No messages yet.
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Event Timeline ──────────────────────────────────── */

export function EventTimeline({ events }: { events: EventItem[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) wasAtBottom.current = isNearBottom(el);
  }, []);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [events]);

  return (
    <div style={{ background: "#111", border: "1px solid #1a1a1a", borderRadius: "3px", padding: "6px" }}>
      <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#555", letterSpacing: "1px", marginBottom: "4px" }}>
        EVENTS
      </h2>
      <div ref={scrollRef} onScroll={handleScroll} style={{ maxHeight: "500px", overflowY: "auto" }}>
        {events.map((evt) => {
          const color = EVENT_COLORS[evt.event_type] ?? "#555";
          return (
            <div key={evt.id} style={{ borderLeft: `2px solid ${color}`, marginBottom: "1px" }}>
              <button
                onClick={() => toggle(evt.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  width: "100%",
                  padding: "2px 4px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "inherit",
                  fontSize: "11px",
                  color: "#b0b0b0",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#0a0a0a")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "4px", minWidth: 0, flex: 1 }}>
                  <span style={{ color: "#444", fontSize: "9px" }}>
                    {expanded.has(evt.id) ? "\u25BC" : "\u25B6"}
                  </span>
                  <span style={{ color, fontWeight: 700, letterSpacing: "0.5px", flexShrink: 0, fontSize: "11px" }}>
                    {evt.event_type}
                  </span>
                  {eventSummary(evt) && (
                    <span style={{ color: "#666", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {eventSummary(evt)}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                  {evt.duration_ms != null && (
                    <span style={{ color: "#444", fontSize: "10px" }}>{evt.duration_ms}ms</span>
                  )}
                  <span style={{ color: "#686", fontSize: "10px" }}>{evt.module}</span>
                  <span style={{ color: "#333", fontSize: "10px" }}>{fmtTime(evt.timestamp)}</span>
                </div>
              </button>
              {expanded.has(evt.id) && (
                <div style={{ padding: "0 4px 4px" }}>
                  <pre
                    style={{
                      fontSize: "10px",
                      color: "#555",
                      background: "#0a0a0a",
                      border: "1px solid #1a1a1a",
                      borderRadius: "2px",
                      padding: "4px",
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
          <div style={{ color: "#333", textAlign: "center", padding: "8px", fontSize: "11px" }}>
            No events yet.
          </div>
        )}
      </div>
    </div>
  );
}
