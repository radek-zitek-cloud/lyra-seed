"use client";

import { STATUS_COLORS, type GraphAgent } from "./graphUtils";

interface DashboardHeaderProps {
  agents: GraphAgent[];
}

export function DashboardHeader({ agents }: DashboardHeaderProps) {
  const counts: Record<string, number> = {};
  for (const a of agents) {
    counts[a.status] = (counts[a.status] ?? 0) + 1;
  }
  const hitlCount = counts["waiting_hitl"] ?? 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 20,
        padding: "6px 16px",
        borderBottom: "1px solid #1a1a1a",
        background: "#111",
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace",
        flexShrink: 0,
      }}
    >
      <span style={{ color: "#e0e0e0" }}>
        AGENTS: <strong>{agents.length}</strong>
      </span>

      {["running", "idle", "waiting_hitl", "completed", "failed"].map((status) => {
        const c = counts[status] ?? 0;
        if (c === 0) return null;
        return (
          <span key={status} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: STATUS_COLORS[status],
              }}
            />
            <span style={{ color: "#888" }}>
              {c} {status.replace("_", " ")}
            </span>
          </span>
        );
      })}

      {hitlCount > 0 && (
        <span style={{ color: "#ffaa00", fontWeight: 700 }}>
          {hitlCount} PENDING HITL
        </span>
      )}
    </div>
  );
}
