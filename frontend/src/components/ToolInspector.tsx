"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function fmtTime(ts?: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toISOString().slice(11, 19);
}

interface ToolEvent {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: {
    tool_name: string;
    arguments?: Record<string, unknown>;
    success?: boolean;
    result?: unknown;
    output?: unknown;
    error?: string;
  };
  duration_ms?: number | null;
}

/** Build a rich inline summary from both call args and result. */
function toolCallSummary(call: ToolEvent, result?: ToolEvent): string {
  const parts: string[] = [];

  // Summarize input arguments — show first 60 chars of JSON
  const args = call.payload.arguments;
  if (args && typeof args === "object") {
    const json = JSON.stringify(args);
    parts.push(json.length > 60 ? json.slice(0, 60) + "…" : json);
  }

  // Summarize result
  if (result) {
    const rp = result.payload;
    if (rp.success === false && rp.error) {
      parts.push(`err: ${String(rp.error).slice(0, 40)}`);
    } else {
      const output = rp.result ?? rp.output;
      if (typeof output === "string" && output.length > 0) {
        parts.push(`→ ${output.slice(0, 50)}`);
      }
    }
  }

  return parts.join("  ");
}

function isNearBottom(el: HTMLElement, threshold = 30): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

export function ToolInspector({ toolEvents }: { toolEvents: ToolEvent[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const calls: { call: ToolEvent; result?: ToolEvent }[] = [];
  for (let i = 0; i < toolEvents.length; i++) {
    const evt = toolEvents[i];
    if (evt.event_type === "tool_call") {
      const next = toolEvents[i + 1];
      if (next?.event_type === "tool_result") {
        calls.push({ call: evt, result: next });
        i++;
      } else {
        calls.push({ call: evt });
      }
    }
  }

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
  }, [toolEvents]);

  return (
    <div style={{ background: "#111", border: "1px solid #1a1a1a", borderRadius: "3px", padding: "6px", marginTop: "6px" }}>
      <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#555", letterSpacing: "1px", marginBottom: "4px" }}>
        TOOL CALLS
      </h2>
      <div ref={scrollRef} onScroll={handleScroll} style={{ maxHeight: "400px", overflowY: "auto" }}>
      {calls.map(({ call, result }) => {
        const isSuccess = result?.payload?.success;
        const statusColor =
          isSuccess === true ? "#00ff41" : isSuccess === false ? "#ff3333" : "#555";
        const statusLabel =
          isSuccess === true ? "ok" : isSuccess === false ? "fail" : "…";

        return (
          <div key={call.id} style={{ borderLeft: "2px solid #aa66ff", marginBottom: "1px" }}>
            <button
              onClick={() => toggle(call.id)}
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
                  {expanded.has(call.id) ? "\u25BC" : "\u25B6"}
                </span>
                <span style={{ color: "#e0e0e0", fontWeight: 700, flexShrink: 0, fontSize: "11px" }}>
                  {call.payload.tool_name}
                </span>
                <span style={{ color: "#666", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {toolCallSummary(call, result)}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
                {result?.duration_ms != null && (
                  <span style={{ color: "#444", fontSize: "10px" }}>{result.duration_ms}ms</span>
                )}
                <span style={{ color: "#333", fontSize: "10px" }}>{fmtTime(call.timestamp)}</span>
                <span style={{ fontSize: "10px", fontWeight: 700, color: statusColor }}>{statusLabel}</span>
              </div>
            </button>
            {expanded.has(call.id) && (
              <div style={{ padding: "0 4px 4px" }}>
                <div style={{ marginBottom: "2px" }}>
                  <div style={{ fontSize: "10px", color: "#555", letterSpacing: "0.5px", marginBottom: "2px" }}>INPUT</div>
                  <pre style={{ fontSize: "10px", color: "#555", background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: "2px", padding: "4px", overflowX: "auto", whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(call.payload.arguments, null, 2)}
                  </pre>
                </div>
                {result && (
                  <div>
                    <div style={{ fontSize: "10px", color: "#555", letterSpacing: "0.5px", marginBottom: "2px" }}>OUTPUT</div>
                    <pre style={{ fontSize: "10px", color: "#555", background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: "2px", padding: "4px", overflowX: "auto", whiteSpace: "pre-wrap" }}>
                      {JSON.stringify(result.payload.result ?? result.payload.output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {calls.length === 0 && (
        <div style={{ color: "#333", textAlign: "center", padding: "8px", fontSize: "11px" }}>
          No tool calls yet.
        </div>
      )}
      </div>
    </div>
  );
}
