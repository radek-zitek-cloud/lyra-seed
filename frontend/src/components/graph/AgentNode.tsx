"use client";

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import {
  STATUS_COLORS,
  SUBTASK_STATUS_COLORS,
  type GraphOrchestration,
} from "./graphUtils";

interface AgentNodeData {
  name: string;
  status: string;
  model: string;
  orchestration: GraphOrchestration | null;
  [key: string]: unknown;
}

function AgentNodeComponent({ data }: { data: AgentNodeData }) {
  const borderColor = STATUS_COLORS[data.status] ?? "#555";
  const orch = data.orchestration;

  return (
    <div
      style={{
        background: "#111",
        border: `2px solid ${borderColor}`,
        borderRadius: 4,
        padding: 0,
        minWidth: 220,
        fontFamily: "'JetBrains Mono', monospace",
        cursor: "pointer",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#333" }} />

      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 10px",
          borderBottom: orch ? "1px solid #1a1a1a" : "none",
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 700, color: "#e0e0e0" }}>
          {data.name}
        </span>
        <span
          data-testid="status-badge"
          style={{
            fontSize: 9,
            color: borderColor,
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          {data.status}
        </span>
      </div>

      {/* Model */}
      <div style={{ padding: "2px 10px 4px", fontSize: 9, color: "#666" }}>
        {data.model}
      </div>

      {/* Subtasks */}
      {orch && orch.subtasks.length > 0 && (
        <div style={{ padding: "4px 8px 6px", borderTop: "1px solid #1a1a1a" }}>
          {orch.subtasks.map((st) => {
            const stColor = SUBTASK_STATUS_COLORS[st.status] ?? "#555";
            return (
              <div
                key={st.id}
                data-testid="subtask-row"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "2px 0",
                  fontSize: 9,
                }}
              >
                <span
                  data-testid={`subtask-dot-${st.status}`}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: stColor,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    color: "#b0b0b0",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                  }}
                >
                  {st.description.length > 35
                    ? st.description.slice(0, 35) + "..."
                    : st.description}
                </span>
                <span style={{ color: stColor, textTransform: "uppercase", fontSize: 8 }}>
                  {st.status}
                </span>
              </div>
            );
          })}
          {orch.synthesized && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 0 0",
                fontSize: 9,
                borderTop: "1px solid #1a1a1a",
                marginTop: 4,
              }}
            >
              <span style={{ color: "#6688ff" }}>{">"}</span>
              <span style={{ color: "#6688ff" }}>SYNTHESIS</span>
              <span style={{ color: "#6688ff", fontSize: 8, marginLeft: "auto" }}>
                COMPLETED
              </span>
            </div>
          )}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ background: "#333" }} />
    </div>
  );
}

export const AgentNode = memo(AgentNodeComponent);
