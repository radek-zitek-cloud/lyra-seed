import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";

// --- Types ---

export interface GraphAgent {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  parent_agent_id: string | null;
}

export interface GraphMessage {
  id: string;
  from_agent_id: string;
  to_agent_id: string;
  content: string;
  message_type: string;
  timestamp: string;
}

export interface GraphSubtask {
  id: string;
  description: string;
  status: string;
  dependencies: number[];
}

export interface GraphOrchestration {
  agent_id: string;
  plan_id: string;
  strategy: string;
  subtasks: GraphSubtask[];
  synthesized: boolean;
}

export interface GraphFilters {
  messageTypes: Set<string>;
  timeRangeMinutes: number | null; // null = all
  showMessages: boolean;
  showSubtasks: boolean;
}

// --- Status Colors ---

export const STATUS_COLORS: Record<string, string> = {
  idle: "#555",
  running: "#00ff41",
  waiting_hitl: "#ffaa00",
  completed: "#6688ff",
  failed: "#ff3333",
};

export const SUBTASK_STATUS_COLORS: Record<string, string> = {
  pending: "#555",
  running: "#00ff41",
  completed: "#6688ff",
  failed: "#ff3333",
  skipped: "#888",
};

export const MESSAGE_TYPE_COLORS: Record<string, string> = {
  task: "#aa66ff",
  result: "#00ff41",
  question: "#ffaa00",
  answer: "#6688ff",
  guidance: "#00ccff",
  status_update: "#888",
};

// --- Node/Edge Builders ---

const NODE_WIDTH = 240;
const NODE_BASE_HEIGHT = 60;
const SUBTASK_ROW_HEIGHT = 22;

export function buildNodes(
  agents: GraphAgent[],
  orchestrations: GraphOrchestration[],
  showSubtasks: boolean,
): Node[] {
  const orchMap = new Map<string, GraphOrchestration>();
  for (const o of orchestrations) {
    orchMap.set(o.agent_id, o);
  }

  return agents.map((agent) => {
    const orch = showSubtasks ? orchMap.get(agent.id) : undefined;
    const subtaskCount = orch?.subtasks.length ?? 0;
    const height = NODE_BASE_HEIGHT + (subtaskCount > 0 ? 20 + subtaskCount * SUBTASK_ROW_HEIGHT : 0);

    return {
      id: agent.id,
      type: "agentNode",
      position: { x: 0, y: 0 },
      data: {
        name: agent.name,
        status: agent.status,
        model: (agent.config?.model as string) ?? "",
        orchestration: orch ?? null,
      },
      style: { width: NODE_WIDTH, height },
    };
  });
}

export function buildEdges(
  agents: GraphAgent[],
  messages: GraphMessage[],
  filters: GraphFilters,
): Edge[] {
  const edges: Edge[] = [];

  // Parent-child edges
  for (const agent of agents) {
    if (agent.parent_agent_id) {
      edges.push({
        id: `pc-${agent.parent_agent_id}-${agent.id}`,
        source: agent.parent_agent_id,
        target: agent.id,
        sourceHandle: "bottom",
        targetHandle: "top",
        type: "parentChild",
        data: { childStatus: agent.status },
      });
    }
  }

  // Message edges
  if (filters.showMessages) {
    const now = Date.now();
    const cutoff = filters.timeRangeMinutes
      ? now - filters.timeRangeMinutes * 60 * 1000
      : 0;

    // Deduplicate: group by (from, to), keep most recent
    const msgGroups = new Map<string, { msg: GraphMessage; count: number }>();

    for (const msg of messages) {
      if (!filters.messageTypes.has(msg.message_type)) continue;
      if (cutoff && new Date(msg.timestamp).getTime() < cutoff) continue;

      const key = `${msg.from_agent_id}->${msg.to_agent_id}`;
      const existing = msgGroups.get(key);
      if (!existing || new Date(msg.timestamp) > new Date(existing.msg.timestamp)) {
        msgGroups.set(key, { msg, count: (existing?.count ?? 0) + 1 });
      } else {
        existing.count++;
      }
    }

    for (const [, { msg, count }] of msgGroups) {
      const isRecent = now - new Date(msg.timestamp).getTime() < 30_000;
      edges.push({
        id: `msg-${msg.id}`,
        source: msg.from_agent_id,
        target: msg.to_agent_id,
        sourceHandle: "msg-source",
        targetHandle: "msg-target",
        type: "message",
        animated: isRecent,
        label: count > 1 ? `${msg.message_type} (${count})` : msg.message_type,
        data: { messageType: msg.message_type, count, isRecent },
      });
    }
  }

  return edges;
}

export function layoutGraph(
  nodes: Node[],
  edges: Edge[],
): { nodes: Node[]; edges: Edge[] } {
  if (nodes.length === 0) return { nodes, edges };

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80 });

  for (const node of nodes) {
    const w = (node.style?.width as number) ?? NODE_WIDTH;
    const h = (node.style?.height as number) ?? NODE_BASE_HEIGHT;
    g.setNode(node.id, { width: w, height: h });
  }

  // Only use parent-child edges for layout (messages create visual clutter in layout)
  for (const edge of edges) {
    if (edge.type === "parentChild") {
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  const laidOut = nodes.map((node) => {
    const pos = g.node(node.id);
    const w = (node.style?.width as number) ?? NODE_WIDTH;
    const h = (node.style?.height as number) ?? NODE_BASE_HEIGHT;
    return {
      ...node,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
    };
  });

  return { nodes: laidOut, edges };
}

export const DEFAULT_FILTERS: GraphFilters = {
  messageTypes: new Set(["task", "result", "question", "answer", "guidance", "status_update"]),
  timeRangeMinutes: 60,
  showMessages: true,
  showSubtasks: true,
};
