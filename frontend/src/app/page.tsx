"use client";

import { useEffect, useState } from "react";

import { AgentList } from "@/components/AgentList";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { useEventStream } from "@/hooks/useEventStream";
import { createAgent, deleteAgent, fetchAgentCost, fetchAgents } from "@/lib/api";

export default function HomePage() {
  const [agents, setAgents] = useState<
    {
      id: string;
      name: string;
      status: string;
      config: Record<string, unknown>;
      created_at: string;
      updated_at: string;
    }[]
  >([]);
  const [agentCosts, setAgentCosts] = useState<Record<string, number>>({});
  const [newName, setNewName] = useState("");
  const { connectionState } = useEventStream();

  const refreshAll = async () => {
    const agentList = await fetchAgents();
    setAgents(agentList);
    // Fetch cost for each agent
    const costs: Record<string, number> = {};
    await Promise.all(
      agentList.map(async (a: { id: string }) => {
        try {
          const c = await fetchAgentCost(a.id);
          costs[a.id] = c.total_cost_usd ?? 0;
        } catch {
          costs[a.id] = 0;
        }
      }),
    );
    setAgentCosts(costs);
  };

  useEffect(() => {
    refreshAll().catch(() => {});
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await createAgent(newName.trim());
    setNewName("");
    await refreshAll();
  };

  const handleDelete = async (id: string) => {
    await deleteAgent(id);
    await refreshAll();
  };

  const totalCost = Object.values(agentCosts).reduce((s, c) => s + c, 0);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <h1
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "#888",
              letterSpacing: "1px",
            }}
          >
            AGENTS
          </h1>
          {totalCost > 0 && (
            <span style={{ fontSize: "12px", color: "#cc9933" }}>
              total ${totalCost.toFixed(4)}
            </span>
          )}
        </div>
        <ConnectionStatus state={connectionState} />
      </div>

      <form
        onSubmit={handleCreate}
        style={{ display: "flex", gap: "8px", marginBottom: "24px" }}
      >
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New agent name..."
          style={{
            flex: 1,
            padding: "8px 10px",
            background: "#0a0a0a",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#e0e0e0",
            fontFamily: "inherit",
            fontSize: "13px",
            outline: "none",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "#00ff41")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "#222")}
        />
        <button
          type="submit"
          disabled={!newName.trim()}
          style={{
            padding: "8px 14px",
            background: "rgba(0, 255, 65, 0.1)",
            border: "1px solid rgba(0, 255, 65, 0.3)",
            borderRadius: "2px",
            color: "#00ff41",
            fontFamily: "inherit",
            fontSize: "12px",
            fontWeight: 700,
            letterSpacing: "1px",
            cursor: !newName.trim() ? "not-allowed" : "pointer",
            opacity: !newName.trim() ? 0.4 : 1,
          }}
        >
          CREATE
        </button>
      </form>

      <AgentList agents={agents} agentCosts={agentCosts} onDelete={handleDelete} />
    </div>
  );
}
