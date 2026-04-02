"use client";

import { useState } from "react";

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

  return (
    <div style={{ background: "#111", border: "1px solid rgba(255,170,0,0.2)", borderRadius: "3px", padding: "6px" }}>
      {pendingActions.map((action) => {
        const argsJson = action.payload.arguments ? JSON.stringify(action.payload.arguments) : "";
        const argsPreview = argsJson.length > 80 ? argsJson.slice(0, 80) + "…" : argsJson;
        return (
          <div key={action.id} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "2px 0" }}>
            <span style={{ color: "#ffcc33", fontWeight: 700, fontSize: "11px", letterSpacing: "0.5px", flexShrink: 0 }}>
              APPROVE?
            </span>
            <span style={{ color: "#ffdd66", fontWeight: 700, fontSize: "11px", flexShrink: 0 }}>
              {action.payload.tool_name}
            </span>
            <span style={{ color: "#cc9933", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>
              {argsPreview}
            </span>
            <div style={{ display: "flex", gap: "4px", marginLeft: "auto", flexShrink: 0, alignItems: "center" }}>
              <input
                type="text"
                placeholder="message..."
                value={messages[action.id] ?? ""}
                onChange={(e) => setMessages((prev) => ({ ...prev, [action.id]: e.target.value }))}
                style={{
                  width: "120px",
                  padding: "2px 6px",
                  background: "#0a0a0a",
                  border: "1px solid rgba(255,170,0,0.3)",
                  borderRadius: "2px",
                  color: "#e0e0e0",
                  fontFamily: "inherit",
                  fontSize: "10px",
                  outline: "none",
                }}
              />
              <button
                onClick={() => onRespond(action.agent_id, true, messages[action.id])}
                style={{
                  padding: "2px 8px",
                  background: "rgba(0,255,65,0.1)",
                  border: "1px solid rgba(0,255,65,0.3)",
                  borderRadius: "2px",
                  color: "#00ff41",
                  fontFamily: "inherit",
                  fontSize: "10px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                OK
              </button>
              <button
                onClick={() => onRespond(action.agent_id, false, messages[action.id])}
                style={{
                  padding: "2px 8px",
                  background: "rgba(255,51,51,0.1)",
                  border: "1px solid rgba(255,51,51,0.3)",
                  borderRadius: "2px",
                  color: "#ff3333",
                  fontFamily: "inherit",
                  fontSize: "10px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                NO
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
