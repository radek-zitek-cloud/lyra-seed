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

export function AgentList({ agents }: { agents: Agent[] }) {
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
          <a
            key={agent.id}
            href={`/agents/${agent.id}`}
            style={{
              display: "block",
              background: "#111",
              border: "1px solid #1a1a1a",
              borderRadius: "4px",
              padding: "20px",
              textDecoration: "none",
              color: "inherit",
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
              <span
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#e0e0e0",
                }}
              >
                {agent.name}
              </span>
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
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "8px",
                fontSize: "12px",
              }}
            >
              <span style={{ color: "#555" }}>MODEL</span>
              <span style={{ color: "#b0b0b0", textAlign: "right" }}>
                {String(agent.config?.model ?? "default")}
              </span>
            </div>
          </a>
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
