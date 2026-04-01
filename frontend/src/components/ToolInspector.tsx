"use client";

import { useEffect, useRef, useState } from "react";

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
    output?: unknown;
    error?: string;
  };
  duration_ms?: number | null;
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

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        setTimeout(scrollToBottom, 50);
      }
      return next;
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [toolEvents]);

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #1a1a1a",
        borderRadius: "4px",
        padding: "20px",
        marginTop: "16px",
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
        TOOL CALLS
      </h2>
      <div ref={scrollRef} style={{ maxHeight: "400px", overflowY: "auto" }}>
      {calls.map(({ call, result }) => {
        const isSuccess = result?.payload?.success;
        const statusColor =
          isSuccess === true ? "#00ff41" : isSuccess === false ? "#ff3333" : "#555";
        const statusLabel =
          isSuccess === true ? "success" : isSuccess === false ? "failed" : "pending";

        return (
          <div
            key={call.id}
            style={{
              borderLeft: "3px solid #aa66ff",
              marginBottom: "4px",
            }}
          >
            <button
              onClick={() => toggle(call.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "8px 10px",
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
                  {expanded.has(call.id) ? "\u25BC" : "\u25B6"}
                </span>
                <span style={{ color: "#e0e0e0", fontWeight: 700 }}>
                  {call.payload.tool_name}
                </span>
                {call.duration_ms != null && (
                  <span style={{ color: "#444", fontSize: "11px" }}>{call.duration_ms}ms</span>
                )}
              </div>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  padding: "1px 8px",
                  borderRadius: "2px",
                  letterSpacing: "1px",
                  color: statusColor,
                  background:
                    isSuccess === true
                      ? "rgba(0,255,65,0.08)"
                      : isSuccess === false
                        ? "rgba(255,51,51,0.08)"
                        : "transparent",
                  border: `1px solid ${
                    isSuccess === true
                      ? "rgba(0,255,65,0.2)"
                      : isSuccess === false
                        ? "rgba(255,51,51,0.2)"
                        : "#222"
                  }`,
                }}
              >
                {statusLabel}
              </span>
            </button>
            {expanded.has(call.id) && (
              <div style={{ padding: "0 10px 10px" }}>
                <div style={{ marginBottom: "8px" }}>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#555",
                      letterSpacing: "0.5px",
                      marginBottom: "4px",
                    }}
                  >
                    INPUT
                  </div>
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
                    {JSON.stringify(call.payload.arguments, null, 2)}
                  </pre>
                </div>
                {result && (
                  <div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "#555",
                        letterSpacing: "0.5px",
                        marginBottom: "4px",
                      }}
                    >
                      OUTPUT
                    </div>
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
                      {JSON.stringify(result.payload.output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {calls.length === 0 && (
        <div style={{ color: "#333", textAlign: "center", padding: "16px", fontSize: "12px" }}>
          No tool calls yet.
        </div>
      )}
      </div>
    </div>
  );
}
