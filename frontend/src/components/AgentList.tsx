"use client";

interface Agent {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  idle: {
    color: "#555",
    bg: "rgba(85, 85, 85, 0.08)",
    border: "rgba(85, 85, 85, 0.2)",
  },
  running: {
    color: "#00ff41",
    bg: "rgba(0, 255, 65, 0.08)",
    border: "rgba(0, 255, 65, 0.2)",
  },
  waiting_hitl: {
    color: "#ffaa00",
    bg: "rgba(255, 170, 0, 0.08)",
    border: "rgba(255, 170, 0, 0.2)",
  },
  completed: {
    color: "#00ff41",
    bg: "rgba(0, 255, 65, 0.08)",
    border: "rgba(0, 255, 65, 0.2)",
  },
  failed: {
    color: "#ff3333",
    bg: "rgba(255, 51, 51, 0.08)",
    border: "rgba(255, 51, 51, 0.2)",
  },
};

const DEFAULT_STATUS = { color: "#555", bg: "transparent", border: "#222" };

export function AgentList({
  agents,
  agentCosts,
  onDelete,
}: {
  agents: Agent[];
  agentCosts?: Record<string, number>;
  onDelete?: (id: string) => void;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
        gap: "16px",
      }}
    >
      {agents.map((agent) => {
        const s = STATUS_STYLES[agent.status] ?? DEFAULT_STATUS;
        return (
          <div
            key={agent.id}
            style={{
              background: "#111",
              border: "1px solid #1a1a1a",
              borderRadius: "4px",
              padding: "20px",
              transition: "border-color 0.3s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#333")}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#1a1a1a")}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "12px",
              }}
            >
              <a
                href={`/agents/${agent.id}`}
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#e0e0e0",
                  textDecoration: "none",
                }}
              >
                {agent.name}
              </a>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                {onDelete && (
                  <button
                    onClick={() => onDelete(agent.id)}
                    style={{
                      background: "none",
                      border: "1px solid #222",
                      borderRadius: "2px",
                      padding: "2px 8px",
                      fontFamily: "inherit",
                      fontSize: "11px",
                      color: "#555",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "#ff3333";
                      e.currentTarget.style.borderColor = "#ff3333";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "#555";
                      e.currentTarget.style.borderColor = "#222";
                    }}
                  >
                    DEL
                  </button>
                )}
              </div>
            </div>
            <a
              href={`/agents/${agent.id}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "4px 8px",
                  fontSize: "12px",
                }}
              >
                <span style={{ color: "#888" }}>MODEL</span>
                <span style={{ color: "#b0b0b0", textAlign: "right" }}>
                  {String(agent.config?.model ?? "default")}
                </span>
                {agentCosts && (agentCosts[agent.id] ?? 0) > 0 && (
                  <>
                    <span style={{ color: "#888" }}>COST</span>
                    <span style={{ color: "#cc9933", textAlign: "right" }}>
                      ${agentCosts[agent.id].toFixed(4)}
                    </span>
                  </>
                )}
              </div>
            </a>
          </div>
        );
      })}
      {agents.length === 0 && (
        <p style={{ color: "#333", textAlign: "center", padding: "32px", fontSize: "12px" }}>
          No agents configured.
        </p>
      )}
    </div>
  );
}
