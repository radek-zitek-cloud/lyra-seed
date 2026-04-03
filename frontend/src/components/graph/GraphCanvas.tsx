"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { AgentNode } from "./AgentNode";
import { ParentChildEdge } from "./ParentChildEdge";
import { MessageEdge } from "./MessageEdge";
import { STATUS_COLORS } from "./graphUtils";

const nodeTypes = { agentNode: AgentNode };
const edgeTypes = { parentChild: ParentChildEdge, message: MessageEdge };

interface GraphCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onAgentClick?: (agentId: string) => void;
}

export function GraphCanvas({ nodes, edges, onAgentClick }: GraphCanvasProps) {
  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      onAgentClick?.(node.id);
    },
    [onAgentClick],
  );

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={handleNodeClick}
        fitView
        minZoom={0.2}
        maxZoom={2}
        style={{ background: "#0a0a0a" }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1a1a1a" gap={20} />
        <Controls
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 4,
          }}
        />
        <MiniMap
          nodeColor={(node) => {
            const status = (node.data as Record<string, unknown>)?.status as string;
            return STATUS_COLORS[status] ?? "#555";
          }}
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 4,
          }}
          maskColor="#0a0a0a88"
        />
      </ReactFlow>
    </div>
  );
}
