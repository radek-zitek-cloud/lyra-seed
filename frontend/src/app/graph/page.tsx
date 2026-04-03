"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useGraphData } from "@/hooks/useGraphData";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { DashboardHeader } from "@/components/graph/DashboardHeader";
import { GraphFilters } from "@/components/graph/GraphFilters";
import { SpawnAgentForm } from "@/components/graph/SpawnAgentForm";
import {
  buildNodes,
  buildEdges,
  layoutGraph,
  DEFAULT_FILTERS,
  type GraphFilters as FiltersType,
} from "@/components/graph/graphUtils";

export default function GraphPage() {
  const router = useRouter();
  const { agents, messages, orchestrations, connectionState, connect, disconnect, refresh } =
    useGraphData();
  const [filters, setFilters] = useState<FiltersType>(DEFAULT_FILTERS);

  const { nodes, edges } = useMemo(() => {
    const rawNodes = buildNodes(agents, orchestrations, filters.showSubtasks);
    const rawEdges = buildEdges(agents, messages, filters);
    return layoutGraph(rawNodes, rawEdges);
  }, [agents, messages, orchestrations, filters]);

  const handleAgentClick = useCallback(
    (agentId: string) => {
      router.push(`/agents/${agentId}`);
    },
    [router],
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <DashboardHeader agents={agents} />

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Graph canvas */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <GraphCanvas nodes={nodes} edges={edges} onAgentClick={handleAgentClick} />
        </div>

        {/* Sidebar */}
        <div
          style={{
            width: 240,
            borderLeft: "1px solid #1a1a1a",
            background: "#111",
            overflowY: "auto",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <GraphFilters filters={filters} onChange={setFilters} />
          <SpawnAgentForm onCreated={refresh} />

          {/* Connection status */}
          <div
            style={{
              padding: "8px 12px",
              borderTop: "1px solid #1a1a1a",
              marginTop: "auto",
            }}
          >
            <button
              onClick={connectionState === "connected" ? disconnect : connect}
              style={{
                background: "transparent",
                border: `1px solid ${connectionState === "connected" ? "#00ff41" : "#555"}`,
                color: connectionState === "connected" ? "#00ff41" : "#555",
                padding: "3px 8px",
                borderRadius: 2,
                fontSize: 9,
                cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
                width: "100%",
              }}
            >
              {connectionState === "connected"
                ? "LIVE"
                : connectionState === "connecting"
                  ? "CONNECTING..."
                  : "OFFLINE"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
