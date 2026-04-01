"use client";

import { useEffect, useRef, useState } from "react";

interface HITLEvent {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: {
    tool_name: string;
    arguments?: Record<string, unknown>;
  };
}

interface HITLPanelProps {
  pendingActions: HITLEvent[];
  onRespond: (agentId: string, approved: boolean, message?: string) => void;
}

export function HITLPanel({ pendingActions, onRespond }: HITLPanelProps) {
  const [messages, setMessages] = useState<Record<string, string>>({});

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [pendingActions]);

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
          color: "#ffaa00",
          letterSpacing: "1px",
          marginBottom: "16px",
        }}
      >
        PENDING APPROVALS
      </h2>
      <div ref={scrollRef} style={{ maxHeight: "400px", overflowY: "auto" }}>
      {pendingActions.map((action) => (
        <div
          key={action.id}
          style={{
            background: "rgba(255, 170, 0, 0.04)",
            border: "1px solid rgba(255, 170, 0, 0.15)",
            borderRadius: "4px",
            padding: "16px",
            marginBottom: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "10px",
            }}
          >
            <span style={{ fontWeight: 700, color: "#e0e0e0", fontSize: "13px" }}>
              {action.payload.tool_name}
            </span>
            <span style={{ fontSize: "11px", color: "#444" }}>
              Agent: {action.agent_id.slice(0, 8)}...
            </span>
          </div>
          {action.payload.arguments && (
            <pre
              style={{
                fontSize: "11px",
                color: "#555",
                background: "#0a0a0a",
                border: "1px solid #1a1a1a",
                borderRadius: "2px",
                padding: "10px",
                marginBottom: "12px",
                overflowX: "auto",
              }}
            >
              {JSON.stringify(action.payload.arguments, null, 2)}
            </pre>
          )}
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Optional message..."
              value={messages[action.id] ?? ""}
              onChange={(e) =>
                setMessages((prev) => ({ ...prev, [action.id]: e.target.value }))
              }
              style={{
                flex: 1,
                padding: "6px 10px",
                background: "#0a0a0a",
                border: "1px solid #222",
                borderRadius: "2px",
                color: "#e0e0e0",
                fontFamily: "inherit",
                fontSize: "12px",
                outline: "none",
              }}
            />
            <button
              onClick={() => onRespond(action.agent_id, true, messages[action.id])}
              style={{
                padding: "6px 14px",
                background: "rgba(0, 255, 65, 0.1)",
                border: "1px solid rgba(0, 255, 65, 0.3)",
                borderRadius: "2px",
                color: "#00ff41",
                fontFamily: "inherit",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "1px",
                cursor: "pointer",
              }}
            >
              Approve
            </button>
            <button
              onClick={() => onRespond(action.agent_id, false, messages[action.id])}
              style={{
                padding: "6px 14px",
                background: "rgba(255, 51, 51, 0.1)",
                border: "1px solid rgba(255, 51, 51, 0.3)",
                borderRadius: "2px",
                color: "#ff3333",
                fontFamily: "inherit",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "1px",
                cursor: "pointer",
              }}
            >
              Deny
            </button>
          </div>
        </div>
      ))}
      {pendingActions.length === 0 && (
        <div style={{ color: "#333", textAlign: "center", padding: "16px", fontSize: "12px" }}>
          No pending approvals.
        </div>
      )}
      </div>
    </div>
  );
}
