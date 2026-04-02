/**
 * Smoke tests for V2 Phase 2 — Inter-Agent Communication.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const mockFetch = vi.fn();
global.fetch = mockFetch;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("V2 Phase 2 — Inter-Agent Communication", () => {
  test("ST-V2-2.15: MessagePanel renders messages with type badges", async () => {
    const { MessagePanel } = await import("@/components/MessagePanel");

    const messages = [
      {
        id: "m1",
        from_agent_id: "a1",
        to_agent_id: "a2",
        content: "Do this task",
        message_type: "task",
        timestamp: "2026-04-02T10:00:00Z",
        in_reply_to: null,
      },
      {
        id: "m2",
        from_agent_id: "a2",
        to_agent_id: "a1",
        content: "Here are the results",
        message_type: "result",
        timestamp: "2026-04-02T10:01:00Z",
        in_reply_to: "m1",
      },
    ];

    render(
      <MessagePanel
        messages={messages}
        currentAgentId="a1"
        onSend={vi.fn()}
      />,
    );

    expect(screen.getByText("Do this task")).toBeInTheDocument();
    expect(screen.getByText("Here are the results")).toBeInTheDocument();
    expect(screen.getByText("task")).toBeInTheDocument();
    expect(screen.getByText("result")).toBeInTheDocument();
  });

  test("ST-V2-2.16: MessagePanel send input", async () => {
    const { MessagePanel } = await import("@/components/MessagePanel");

    render(
      <MessagePanel
        messages={[]}
        currentAgentId="a1"
        onSend={vi.fn()}
      />,
    );

    // Send button exists
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });
});
