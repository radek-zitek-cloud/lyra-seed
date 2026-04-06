"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  llm_token: "#5577cc",
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
        const cost = p.cost_usd != null ? ` $${Number(p.cost_usd).toFixed(4)}` : "";
        return `in=${inTok} out=${outTok}${cost}`;
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

export function ConversationPanel({ messages, streamingContent }: { messages: Message[]; streamingContent?: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) wasAtBottom.current = isNearBottom(el);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages, streamingContent]);

  return (
    <div style={{ background: "#111", border: "1px solid #1a1a1a", borderRadius: "3px", padding: "6px", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#888", letterSpacing: "1px", marginBottom: "4px", flexShrink: 0 }}>
        CONVERSATION
      </h2>
      <div ref={scrollRef} onScroll={handleScroll} style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {messages.filter((msg) => {
          if (msg.role === "tool_result" || msg.role === "system") return false;
          // Hide assistant tool-calling turns with no visible content
          if (msg.role === "assistant" && msg.tool_calls && !msg.content) return false;
          return true;
        }).map((msg, i) => {
          // Detect auto-wake messages (injected by message bus)
          const content = String(msg.content ?? "");
          const isAgentMessage =
            msg.role === "human" &&
            /^\[(?:task|result|guidance|question|answer|status_update) from /.test(content);
          const displayRole = isAgentMessage ? "message" : msg.role;
          const roleColor = isAgentMessage ? "#ffaa00" : (ROLE_COLORS[msg.role] ?? "#888");
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
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "6px",
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ color: roleColor, fontWeight: 700, fontSize: "10px", letterSpacing: "0.5px", textTransform: "uppercase", marginRight: "6px" }}>
                  {displayRole}:
                </span>
                <span style={{ color: "#d0d0d0", whiteSpace: "pre-wrap" }}>
                  {msg.content}
                </span>
              </div>
              {msg.timestamp && (
                <span style={{ color: "#666", fontSize: "10px", flexShrink: 0 }}>{fmtTime(msg.timestamp)}</span>
              )}
            </div>
          );
        })}
        {streamingContent && (
          <div
            style={{
              padding: "2px 4px",
              marginBottom: "1px",
              borderLeft: "2px solid #00ff41",
              background: "#0a0a0a",
              fontSize: "12px",
              lineHeight: "1.4",
            }}
          >
            <span style={{ color: "#00ff41", fontWeight: 700, fontSize: "10px", letterSpacing: "0.5px", textTransform: "uppercase", marginRight: "6px" }}>
              ASSISTANT:
            </span>
            <span style={{ color: "#d0d0d0", whiteSpace: "pre-wrap" }}>
              {streamingContent}
            </span>
            <span style={{ display: "inline-block", width: "6px", height: "12px", background: "#00ff41", marginLeft: "2px", animation: "blink 1s step-end infinite", verticalAlign: "text-bottom" }} />
          </div>
        )}
        {!streamingContent && messages.filter((m) => {
          if (m.role === "tool_result" || m.role === "system") return false;
          if (m.role === "assistant" && m.tool_calls && !m.content) return false;
          return true;
        }).length === 0 && (
          <div style={{ color: "#555", textAlign: "center", padding: "8px", fontSize: "11px" }}>
            No messages yet.
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Event Timeline ──────────────────────────────────── */

function FilterChip({ label, active, color, onClick }: {
  label: string; active: boolean; color: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: "9px",
        fontWeight: 700,
        padding: "1px 5px",
        borderRadius: "2px",
        border: `1px solid ${active ? color : "#333"}`,
        background: active ? `${color}18` : "transparent",
        color: active ? color : "#555",
        cursor: "pointer",
        fontFamily: "inherit",
        letterSpacing: "0.3px",
        lineHeight: "14px",
      }}
    >
      {label}
    </button>
  );
}

const STORAGE_KEY_TYPES = "lyra-event-filter-types";
const STORAGE_KEY_MODULES = "lyra-event-filter-modules";
const STORAGE_KEY_OPEN = "lyra-event-filter-open";

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return new Set(JSON.parse(raw));
  } catch { /* ignore */ }
  return new Set();
}

function saveSet(key: string, s: Set<string>) {
  try { localStorage.setItem(key, JSON.stringify([...s])); } catch { /* ignore */ }
}

export function EventTimeline({ events }: { events: EventItem[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(() => loadSet(STORAGE_KEY_TYPES));
  const [hiddenModules, setHiddenModules] = useState<Set<string>>(() => loadSet(STORAGE_KEY_MODULES));
  const [showFilters, setShowFilters] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY_OPEN) === "1"; } catch { return false; }
  });
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

  const toggleType = (t: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      saveSet(STORAGE_KEY_TYPES, next);
      return next;
    });
  };

  const toggleModule = (m: string) => {
    setHiddenModules((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m); else next.add(m);
      saveSet(STORAGE_KEY_MODULES, next);
      return next;
    });
  };

  // Collect unique types and modules from events
  const eventTypes = useMemo(() => {
    const s = new Set<string>();
    for (const e of events) s.add(e.event_type);
    return Array.from(s).sort();
  }, [events]);

  const modules = useMemo(() => {
    const s = new Set<string>();
    for (const e of events) if (e.module) s.add(e.module);
    return Array.from(s).sort();
  }, [events]);

  const filtered = useMemo(
    () => events.filter(
      (e) => !hiddenTypes.has(e.event_type) && !hiddenModules.has(e.module),
    ),
    [events, hiddenTypes, hiddenModules],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [filtered]);

  return (
    <div style={{ background: "#111", border: "1px solid #1a1a1a", borderRadius: "3px", padding: "6px", minHeight: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px", flexShrink: 0 }}>
        <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#888", letterSpacing: "1px", margin: 0 }}>
          EVENTS
        </h2>
        <span style={{ fontSize: "10px", color: "#555" }}>
          {filtered.length}/{events.length}
        </span>
        <button
          onClick={() => setShowFilters((v) => {
            const next = !v;
            try { localStorage.setItem(STORAGE_KEY_OPEN, next ? "1" : "0"); } catch { /* ignore */ }
            return next;
          })}
          style={{
            fontSize: "9px",
            fontWeight: 700,
            color: (hiddenTypes.size > 0 || hiddenModules.size > 0) ? "#ffaa00" : "#555",
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: "inherit",
            padding: 0,
            marginLeft: "auto",
          }}
        >
          {showFilters ? "\u25BC" : "\u25B6"} FILTER
        </button>
      </div>
      {showFilters && (
        <div style={{ flexShrink: 0, marginBottom: "4px", display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
            {eventTypes.map((t) => (
              <FilterChip
                key={t}
                label={t}
                active={!hiddenTypes.has(t)}
                color={EVENT_COLORS[t] ?? "#888"}
                onClick={() => toggleType(t)}
              />
            ))}
          </div>
          {modules.length > 1 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
              {modules.map((m) => (
                <FilterChip
                  key={m}
                  label={m}
                  active={!hiddenModules.has(m)}
                  color="#8a8"
                  onClick={() => toggleModule(m)}
                />
              ))}
            </div>
          )}
        </div>
      )}
      <div ref={scrollRef} onScroll={handleScroll} style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {filtered.map((evt) => {
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
                  <span style={{ color: "#777", fontSize: "9px" }}>
                    {expanded.has(evt.id) ? "\u25BC" : "\u25B6"}
                  </span>
                  <span style={{ color, fontWeight: 700, letterSpacing: "0.5px", flexShrink: 0, fontSize: "11px" }}>
                    {evt.event_type}
                  </span>
                  {eventSummary(evt) && (
                    <span style={{ color: "#999", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {eventSummary(evt)}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                  {evt.duration_ms != null && (
                    <span style={{ color: "#777", fontSize: "10px" }}>{evt.duration_ms}ms</span>
                  )}
                  <span style={{ color: "#8a8", fontSize: "10px" }}>{evt.module}</span>
                  <span style={{ color: "#666", fontSize: "10px" }}>{fmtTime(evt.timestamp)}</span>
                </div>
              </button>
              {expanded.has(evt.id) && (
                <div style={{ padding: "0 4px 4px" }}>
                  <pre
                    style={{
                      fontSize: "10px",
                      color: "#888",
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
        {filtered.length === 0 && (
          <div style={{ color: "#333", textAlign: "center", padding: "8px", fontSize: "11px" }}>
            {events.length === 0 ? "No events yet." : "All events filtered."}
          </div>
        )}
      </div>
    </div>
  );
}
