"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ConnectionStatus } from "@/components/ConnectionStatus";
import { useEventStream } from "@/hooks/useEventStream";
import { fetchAgents, fetchGlobalEvents } from "@/lib/api";

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
  message_sent: "#cc6600",
  message_received: "#cc6600",
};

function fmtTime(ts?: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toISOString().slice(11, 19);
}

function eventSummary(evt: EventItem): string {
  const p = evt.payload;
  switch (evt.event_type) {
    case "llm_request":
      if (p.model) return `model=${p.model} msgs=${p.message_count ?? "?"}`;
      if (p.iteration) return `iter=${p.iteration} msgs=${p.message_count ?? "?"}`;
      return "";
    case "llm_response": {
      if (p.usage && typeof p.usage === "object") {
        const u = p.usage as Record<string, unknown>;
        const inTok = u.prompt_tokens ?? u.input_tokens ?? "?";
        const outTok = u.completion_tokens ?? u.output_tokens ?? "?";
        const cost = p.cost_usd != null ? ` $${Number(p.cost_usd).toFixed(4)}` : "";
        return `in=${inTok} out=${outTok}${cost}`;
      }
      if (p.tool_call_count) return `tools=${p.tool_call_count}`;
      return "";
    }
    case "tool_call":
      return (p.tool_name ?? p.tool) ? String(p.tool_name ?? p.tool) : "";
    case "tool_result": {
      const name = (p.tool_name ?? p.tool) ? String(p.tool_name ?? p.tool) : "";
      const ok = p.success !== undefined ? (p.success ? "ok" : "fail") : "";
      const dur = p.duration_ms ? `${p.duration_ms}ms` : "";
      return [name, ok, dur].filter(Boolean).join(" ");
    }
    case "error":
      return p.error ? String(p.error).slice(0, 50) : "";
    case "agent_spawn":
      return p.child_name ? String(p.child_name) : "";
    case "agent_complete":
      return p.status ? String(p.status) : "";
    default:
      return "";
  }
}

function isNearBottom(el: HTMLElement, threshold = 30): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

export default function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState("");
  const [filterModule, setFilterModule] = useState("");
  const [filterAgent, setFilterAgent] = useState("");
  const [agentNames, setAgentNames] = useState<Record<string, string>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);
  const { events: liveEvents, connectionState, connect, disconnect } = useEventStream();

  useEffect(() => {
    fetchGlobalEvents({ limit: 200 })
      .then(setEvents)
      .catch(() => {});
    fetchAgents()
      .then((list: { id: string; name: string }[]) => {
        const map: Record<string, string> = {};
        for (const a of list) map[a.id] = a.name;
        setAgentNames(map);
      })
      .catch(() => {});
  }, []);

  // Merge live events
  useEffect(() => {
    if (liveEvents.length === 0) return;
    setEvents((prev) => {
      const ids = new Set(prev.map((e) => e.id));
      const newEvts = liveEvents.filter((e) => !ids.has(e.id)) as EventItem[];
      return newEvts.length > 0 ? [...prev, ...newEvts] : prev;
    });
  }, [liveEvents]);

  // Auto-scroll
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) wasAtBottom.current = isNearBottom(el);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [events]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const eventTypes = Array.from(new Set(events.map((e) => e.event_type))).sort();
  const modules = Array.from(new Set(events.map((e) => e.module))).sort();
  const agents = Array.from(new Set(events.map((e) => e.agent_id))).sort((a, b) => {
    if (a === "system") return -1;
    if (b === "system") return 1;
    return a.localeCompare(b);
  });
  const filtered = events.filter(
    (e) =>
      (!filterType || e.event_type === filterType) &&
      (!filterModule || e.module === filterModule) &&
      (!filterAgent || e.agent_id === filterAgent),
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px", flexShrink: 0 }}>
        <span style={{ fontSize: "14px", fontWeight: 700, color: "#e0e0e0", letterSpacing: "1px" }}>
          GLOBAL EVENTS
        </span>
        <span style={{ fontSize: "11px", color: "#555" }}>{filtered.length} events</span>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          style={{
            fontSize: "11px",
            background: "#111",
            color: "#888",
            border: "1px solid #222",
            borderRadius: "2px",
            padding: "2px 6px",
          }}
        >
          <option value="">all types</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={filterModule}
          onChange={(e) => setFilterModule(e.target.value)}
          style={{
            fontSize: "11px",
            background: "#111",
            color: "#888",
            border: "1px solid #222",
            borderRadius: "2px",
            padding: "2px 6px",
          }}
        >
          <option value="">all modules</option>
          {modules.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select
          value={filterAgent}
          onChange={(e) => setFilterAgent(e.target.value)}
          style={{
            fontSize: "11px",
            background: "#111",
            color: "#888",
            border: "1px solid #222",
            borderRadius: "2px",
            padding: "2px 6px",
          }}
        >
          <option value="">all sources</option>
          {agents.map((a) => (
            <option key={a} value={a}>{a === "system" ? "system" : agentNames[a] ?? a.slice(0, 8)}</option>
          ))}
        </select>
        <span style={{ marginLeft: "auto" }}>
          <ConnectionStatus state={connectionState} onConnect={connect} onDisconnect={disconnect} />
        </span>
      </div>

      {/* Event list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          background: "#111",
          border: "1px solid #1a1a1a",
          borderRadius: "3px",
          padding: "6px",
        }}
      >
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
                  <span style={{ color: "#999", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {[eventSummary(evt), JSON.stringify(evt.payload).slice(0, 150)].filter(Boolean).join(" — ")}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                  {evt.duration_ms != null && (
                    <span style={{ color: "#777", fontSize: "10px" }}>{evt.duration_ms}ms</span>
                  )}
                  <a
                    href={`/agents/${evt.agent_id}`}
                    onClick={(e) => e.stopPropagation()}
                    style={{ color: "#00ccff", fontSize: "10px", textDecoration: "none" }}
                    title={evt.agent_id}
                  >
                    {agentNames[evt.agent_id] ?? evt.agent_id.slice(0, 8)}
                  </a>
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
            No events yet.
          </div>
        )}
      </div>
    </div>
  );
}
