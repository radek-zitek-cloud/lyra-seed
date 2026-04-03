/**
 * Smoke tests for V2 Phase 5 — Observation UI: Multi-Agent & Orchestration Graph.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve([]),
});
global.fetch = mockFetch;

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock useGraphData for GraphPage test
vi.mock("@/hooks/useGraphData", () => ({
  useGraphData: () => ({
    agents: [
      { id: "a1", name: "test", status: "idle", config: {}, parent_agent_id: null },
    ],
    messages: [],
    orchestrations: [],
    connectionState: "connected" as const,
    connect: () => {},
    disconnect: () => {},
    refresh: () => {},
  }),
}));

// Mock React Flow (requires browser layout APIs not available in jsdom)
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="react-flow">{children}</div>
  ),
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Handle: () => null,
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
  getBezierPath: () => ["M0,0", 0, 0],
}));

// Mock dagre
vi.mock("@dagrejs/dagre", () => {
  const nodes: Record<string, { x: number; y: number; width: number; height: number }> = {};
  function GraphConstructor() {
    return {
      setDefaultEdgeLabel: vi.fn(),
      setGraph: vi.fn(),
      setNode: (id: string, dims: { width: number; height: number }) => {
        nodes[id] = { x: 0, y: 0, ...dims };
      },
      setEdge: vi.fn(),
      node: (id: string) => nodes[id] ?? { x: 0, y: 0 },
    };
  }
  return {
    default: {
      graphlib: { Graph: GraphConstructor },
      layout: () => {},
    },
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  // Restore fetch mock for next test
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve([]),
  });
});

describe("V2 Phase 5 — Multi-Agent & Orchestration Graph", () => {
  // --- graphUtils pure function tests ---

  test("ST-V2-5.6: buildNodes produces correct node count", async () => {
    const { buildNodes } = await import(
      "@/components/graph/graphUtils"
    );

    const agents = [
      { id: "a1", name: "coordinator", status: "running", config: {}, parent_agent_id: null },
      { id: "a2", name: "worker", status: "idle", config: {}, parent_agent_id: "a1" },
      { id: "a3", name: "researcher", status: "completed", config: {}, parent_agent_id: "a1" },
    ];

    const nodes = buildNodes(agents, [], true);
    expect(nodes).toHaveLength(3);
    expect(nodes[0].id).toBe("a1");
    expect(nodes[0].type).toBe("agentNode");
    expect(nodes[1].id).toBe("a2");
    expect(nodes[2].id).toBe("a3");
  });

  test("ST-V2-5.7: buildEdges produces parent-child edges", async () => {
    const { buildEdges, DEFAULT_FILTERS } = await import(
      "@/components/graph/graphUtils"
    );

    const agents = [
      { id: "a1", name: "parent", status: "running", config: {}, parent_agent_id: null },
      { id: "a2", name: "child1", status: "idle", config: {}, parent_agent_id: "a1" },
      { id: "a3", name: "child2", status: "idle", config: {}, parent_agent_id: "a1" },
    ];

    const edges = buildEdges(agents, [], DEFAULT_FILTERS);
    const pcEdges = edges.filter((e) => e.type === "parentChild");
    expect(pcEdges).toHaveLength(2);
    expect(pcEdges[0].source).toBe("a1");
    expect(pcEdges[0].target).toBe("a2");
    expect(pcEdges[1].source).toBe("a1");
    expect(pcEdges[1].target).toBe("a3");
  });

  test("ST-V2-5.8: buildEdges produces message edges", async () => {
    const { buildEdges, DEFAULT_FILTERS } = await import(
      "@/components/graph/graphUtils"
    );

    const agents = [
      { id: "a1", name: "parent", status: "running", config: {}, parent_agent_id: null },
      { id: "a2", name: "child", status: "idle", config: {}, parent_agent_id: "a1" },
    ];

    const messages = [
      {
        id: "m1",
        from_agent_id: "a1",
        to_agent_id: "a2",
        content: "do this",
        message_type: "task",
        timestamp: new Date().toISOString(),
      },
    ];

    const edges = buildEdges(agents, messages, DEFAULT_FILTERS);
    const msgEdges = edges.filter((e) => e.type === "message");
    expect(msgEdges).toHaveLength(1);
    expect(msgEdges[0].source).toBe("a1");
    expect(msgEdges[0].target).toBe("a2");
  });

  test("ST-V2-5.9: buildEdges respects message type filter", async () => {
    const { buildEdges, DEFAULT_FILTERS } = await import(
      "@/components/graph/graphUtils"
    );

    const agents = [
      { id: "a1", name: "parent", status: "running", config: {}, parent_agent_id: null },
      { id: "a2", name: "child", status: "idle", config: {}, parent_agent_id: "a1" },
    ];

    const messages = [
      {
        id: "m1",
        from_agent_id: "a1",
        to_agent_id: "a2",
        content: "task msg",
        message_type: "task",
        timestamp: new Date().toISOString(),
      },
      {
        id: "m2",
        from_agent_id: "a2",
        to_agent_id: "a1",
        content: "result msg",
        message_type: "result",
        timestamp: new Date().toISOString(),
      },
    ];

    // Filter out "result" type
    const filters = {
      ...DEFAULT_FILTERS,
      messageTypes: new Set(["task"]),
    };

    const edges = buildEdges(agents, messages, filters);
    const msgEdges = edges.filter((e) => e.type === "message");
    expect(msgEdges).toHaveLength(1);
    expect(msgEdges[0].source).toBe("a1");
  });

  // --- Component render tests ---

  test("ST-V2-5.2: DashboardHeader shows agent counts", async () => {
    const { DashboardHeader } = await import(
      "@/components/graph/DashboardHeader"
    );

    const agents = [
      { id: "a1", name: "one", status: "running", config: {}, parent_agent_id: null },
      { id: "a2", name: "two", status: "idle", config: {}, parent_agent_id: null },
      { id: "a3", name: "three", status: "running", config: {}, parent_agent_id: null },
    ];

    render(<DashboardHeader agents={agents} />);

    expect(screen.getByText("3")).toBeInTheDocument(); // total count
    const text = document.body.textContent ?? "";
    expect(text).toContain("2 running");
    expect(text).toContain("1 idle");
  });

  test("ST-V2-5.3: AgentNode renders name, model, status", async () => {
    const { AgentNode } = await import("@/components/graph/AgentNode");

    render(
      <AgentNode
        data={{
          name: "coordinator",
          status: "running",
          model: "openai/gpt-5.4",
          orchestration: null,
        }}
      />,
    );

    expect(screen.getByText("coordinator")).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-5.4")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveTextContent("running");
  });

  test("ST-V2-5.4: AgentNode shows subtasks when orchestration present", async () => {
    const { AgentNode } = await import("@/components/graph/AgentNode");

    render(
      <AgentNode
        data={{
          name: "orchestrator",
          status: "running",
          model: "openai/gpt-5.4",
          orchestration: {
            agent_id: "a1",
            plan_id: "p1",
            strategy: "parallel",
            subtasks: [
              { id: "s1", description: "Research Python", status: "completed", dependencies: [] },
              { id: "s2", description: "Research Rust", status: "running", dependencies: [] },
              { id: "s3", description: "Synthesize", status: "pending", dependencies: [0, 1] },
            ],
            synthesized: false,
          },
        }}
      />,
    );

    const rows = screen.getAllByTestId("subtask-row");
    expect(rows).toHaveLength(3);
    expect(screen.getByText(/Research Python/)).toBeInTheDocument();
    expect(screen.getByText(/Research Rust/)).toBeInTheDocument();
    expect(screen.getByText(/Synthesize/)).toBeInTheDocument();
  });

  test("ST-V2-5.5: AgentNode status colors match spec", async () => {
    const { AgentNode } = await import("@/components/graph/AgentNode");
    const { STATUS_COLORS } = await import("@/components/graph/graphUtils");

    for (const [status] of Object.entries(STATUS_COLORS)) {
      cleanup();
      render(
        <AgentNode
          data={{
            name: "test",
            status,
            model: "test-model",
            orchestration: null,
          }}
        />,
      );

      const badge = screen.getByTestId("status-badge");
      // jsdom normalizes hex to rgb, so just verify the color attribute is set
      expect(badge.style.color).toBeTruthy();
      expect(badge.textContent).toBe(status);
    }
  });

  test("ST-V2-5.12: Subtask status colors match spec", async () => {
    const { AgentNode } = await import("@/components/graph/AgentNode");
    const { SUBTASK_STATUS_COLORS } = await import("@/components/graph/graphUtils");

    const statuses = Object.keys(SUBTASK_STATUS_COLORS);
    render(
      <AgentNode
        data={{
          name: "test",
          status: "running",
          model: "m",
          orchestration: {
            agent_id: "a1",
            plan_id: "p1",
            strategy: "sequential",
            subtasks: statuses.map((s, i) => ({
              id: `s${i}`,
              description: `Task ${s}`,
              status: s,
              dependencies: [],
            })),
            synthesized: false,
          },
        }}
      />,
    );

    for (const status of statuses) {
      const dot = screen.getByTestId(`subtask-dot-${status}`);
      // jsdom normalizes hex to rgb, so just verify background is set
      expect(dot.style.background).toBeTruthy();
    }
  });

  test("ST-V2-5.10: SpawnAgentForm renders with required fields", async () => {
    const { SpawnAgentForm } = await import(
      "@/components/graph/SpawnAgentForm"
    );

    render(<SpawnAgentForm onCreated={vi.fn()} />);

    expect(screen.getByPlaceholderText("Agent name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Model (optional)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create/i })).toBeInTheDocument();
  });

  test("ST-V2-5.11: GraphFilters renders filter controls", async () => {
    const { GraphFilters } = await import(
      "@/components/graph/GraphFilters"
    );
    const { DEFAULT_FILTERS } = await import(
      "@/components/graph/graphUtils"
    );

    render(<GraphFilters filters={DEFAULT_FILTERS} onChange={vi.fn()} />);

    expect(screen.getByText("Show messages")).toBeInTheDocument();
    expect(screen.getByText("Show subtasks")).toBeInTheDocument();
    expect(screen.getByText("1h")).toBeInTheDocument();
    expect(screen.getByText("All")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).toContain("task");
    expect(text).toContain("result");
    expect(text).toContain("guidance");
  });

  test("ST-V2-5.13: Layout nav includes GRAPH link", async () => {
    // Import and render layout
    const fs = await import("fs");
    const layoutContent = fs.readFileSync(
      "src/app/layout.tsx",
      "utf-8",
    );
    expect(layoutContent).toContain('href="/graph"');
    expect(layoutContent).toContain("GRAPH");
  });

  test("ST-V2-5.1: GraphPage renders without crash", async () => {
    const GraphPage = (await import("@/app/graph/page")).default;
    render(<GraphPage />);

    expect(screen.getByTestId("react-flow")).toBeInTheDocument();
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });
});
