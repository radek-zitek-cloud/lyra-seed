/**
 * Smoke tests for V1 Phase 5 — Observation UI.
 *
 * Each test maps to a smoke test ID from SMOKE_TESTS.md.
 * All API calls are mocked — no real backend needed.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("V1 Phase 5 — Observation UI", () => {
  test("ST-5.9: Agent list page renders", async () => {
    const { AgentList } = await import("@/components/AgentList");

    const agents = [
      {
        id: "a1",
        name: "Agent Alpha",
        status: "idle",
        config: { model: "test/model" },
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
      {
        id: "a2",
        name: "Agent Beta",
        status: "running",
        config: { model: "test/model" },
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ];

    render(<AgentList agents={agents} />);

    expect(screen.getByText("Agent Alpha")).toBeInTheDocument();
    expect(screen.getByText("Agent Beta")).toBeInTheDocument();
    // Status badges
    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  test("ST-5.10: Agent detail page renders", async () => {
    const { AgentDetail } = await import("@/components/AgentDetail");

    const agent = {
      id: "a1",
      name: "Agent Alpha",
      status: "idle",
      config: { model: "test/model" },
      created_at: "2026-04-01T00:00:00Z",
      updated_at: "2026-04-01T00:00:00Z",
    };

    const messages = [
      { role: "human", content: "Hello", timestamp: "2026-04-01T00:00:00Z" },
      {
        role: "assistant",
        content: "Hi there!",
        timestamp: "2026-04-01T00:00:01Z",
      },
    ];

    const events = [
      {
        id: "e1",
        agent_id: "a1",
        event_type: "llm_request",
        module: "llm",
        timestamp: "2026-04-01T00:00:00Z",
        payload: { model: "test" },
      },
      {
        id: "e2",
        agent_id: "a1",
        event_type: "llm_response",
        module: "llm",
        timestamp: "2026-04-01T00:00:01Z",
        payload: { content: "hello" },
      },
    ];

    render(
      <AgentDetail agent={agent} messages={messages} events={events} />,
    );

    // Agent name and status
    expect(screen.getByText("Agent Alpha")).toBeInTheDocument();
    expect(screen.getByText("idle")).toBeInTheDocument();

    // Conversation messages
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi there!")).toBeInTheDocument();

    // Events in timeline
    expect(screen.getByText("llm_request")).toBeInTheDocument();
    expect(screen.getByText("llm_response")).toBeInTheDocument();
  });

  test("ST-5.11: HITL panel renders with pending actions", async () => {
    const { HITLPanel } = await import("@/components/HITLPanel");

    const pendingActions = [
      {
        id: "e1",
        agent_id: "a1",
        event_type: "hitl_request",
        module: "runtime",
        timestamp: "2026-04-01T00:00:00Z",
        payload: {
          tool_name: "dangerous_tool",
          arguments: { target: "production" },
        },
      },
    ];

    render(<HITLPanel pendingActions={pendingActions} onRespond={vi.fn()} />);

    // Pending action displayed
    expect(screen.getByText("dangerous_tool")).toBeInTheDocument();

    // Approve and Deny buttons
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
  });

  test("ST-5.12: Tool inspector renders", async () => {
    const { ToolInspector } = await import("@/components/ToolInspector");

    const toolCalls = [
      {
        id: "e1",
        agent_id: "a1",
        event_type: "tool_call",
        module: "tools",
        timestamp: "2026-04-01T00:00:00Z",
        payload: {
          tool_name: "search",
          arguments: { query: "test" },
        },
        duration_ms: 150,
      },
      {
        id: "e2",
        agent_id: "a1",
        event_type: "tool_result",
        module: "tools",
        timestamp: "2026-04-01T00:00:01Z",
        payload: {
          tool_name: "search",
          success: true,
          output: "result data",
        },
        duration_ms: null,
      },
    ];

    render(<ToolInspector toolEvents={toolCalls} />);

    // Tool name displayed
    expect(screen.getByText("search")).toBeInTheDocument();

    // Status visible
    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
