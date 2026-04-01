"use client";

import { useState } from "react";

interface Agent {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface Message {
  role: string;
  content: string;
  timestamp?: string;
  tool_calls?: unknown[];
}

interface EventItem {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: Record<string, unknown>;
  duration_ms?: number | null;
  parent_event_id?: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  idle: "bg-gray-200 text-gray-800",
  running: "bg-green-200 text-green-800",
  waiting_hitl: "bg-yellow-200 text-yellow-800",
  completed: "bg-blue-200 text-blue-800",
  failed: "bg-red-200 text-red-800",
};

const EVENT_COLORS: Record<string, string> = {
  llm_request: "border-l-blue-500",
  llm_response: "border-l-blue-300",
  tool_call: "border-l-purple-500",
  tool_result: "border-l-purple-300",
  memory_read: "border-l-green-400",
  memory_write: "border-l-green-600",
  hitl_request: "border-l-yellow-500",
  hitl_response: "border-l-yellow-300",
  error: "border-l-red-500",
};

export function AgentDetail({
  agent,
  messages,
  events,
}: {
  agent: Agent;
  messages: Message[];
  events: EventItem[];
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold">{agent.name}</h1>
          <p className="text-sm text-gray-500">
            Model: {String(agent.config?.model ?? "default")}
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded text-sm font-medium ${STATUS_COLORS[agent.status] ?? "bg-gray-100"}`}
        >
          {agent.status}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Conversation Panel */}
        <div>
          <h2 className="font-semibold mb-3 text-lg">Conversation</h2>
          <div className="space-y-3 border rounded-lg p-4 max-h-96 overflow-y-auto">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg ${
                  msg.role === "human"
                    ? "bg-blue-50 ml-8"
                    : msg.role === "assistant"
                      ? "bg-gray-50 mr-8"
                      : "bg-yellow-50 text-sm"
                }`}
              >
                <span className="text-xs font-medium text-gray-500 uppercase">
                  {msg.role}
                </span>
                <p className="mt-1">{msg.content}</p>
              </div>
            ))}
            {messages.length === 0 && (
              <p className="text-gray-400 text-center">No messages yet.</p>
            )}
          </div>
        </div>

        {/* Event Timeline */}
        <div>
          <h2 className="font-semibold mb-3 text-lg">Events</h2>
          <div className="space-y-2 border rounded-lg p-4 max-h-96 overflow-y-auto">
            {events.map((evt) => (
              <div
                key={evt.id}
                className={`border-l-4 ${EVENT_COLORS[evt.event_type] ?? "border-l-gray-300"}`}
              >
                <button
                  onClick={() => toggle(evt.id)}
                  className="w-full pl-3 py-2 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">
                        {expanded.has(evt.id) ? "\u25BC" : "\u25B6"}
                      </span>
                      <span className="font-mono text-sm font-medium">
                        {evt.event_type}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {evt.duration_ms != null && (
                        <span className="text-xs text-gray-400">
                          {evt.duration_ms}ms
                        </span>
                      )}
                      <span className="text-xs text-gray-400">
                        {evt.module}
                      </span>
                    </div>
                  </div>
                </button>
                {expanded.has(evt.id) && (
                  <div className="pl-3 pb-2 pr-2">
                    <pre className="text-xs bg-white border rounded p-2 overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(evt.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
            {events.length === 0 && (
              <p className="text-gray-400 text-center">No events yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
