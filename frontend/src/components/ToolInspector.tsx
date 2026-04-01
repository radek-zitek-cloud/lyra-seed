"use client";

import { useState } from "react";

interface ToolEvent {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: {
    tool_name: string;
    arguments?: Record<string, unknown>;
    success?: boolean;
    output?: unknown;
    error?: string;
  };
  duration_ms?: number | null;
}

export function ToolInspector({ toolEvents }: { toolEvents: ToolEvent[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Group consecutive tool_call + tool_result pairs
  const calls: { call: ToolEvent; result?: ToolEvent }[] = [];
  for (let i = 0; i < toolEvents.length; i++) {
    const evt = toolEvents[i];
    if (evt.event_type === "tool_call") {
      const next = toolEvents[i + 1];
      if (next?.event_type === "tool_result") {
        calls.push({ call: evt, result: next });
        i++;
      } else {
        calls.push({ call: evt });
      }
    }
  }

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-3">
      <h2 className="font-semibold text-lg">Tool Calls</h2>
      {calls.map(({ call, result }) => {
        const isSuccess = result?.payload?.success;
        return (
          <div key={call.id} className="border rounded-lg overflow-hidden">
            <button
              onClick={() => toggle(call.id)}
              className="w-full p-3 flex items-center justify-between hover:bg-gray-50 text-left"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono font-medium">
                  {call.payload.tool_name}
                </span>
                {call.duration_ms != null && (
                  <span className="text-xs text-gray-400">
                    {call.duration_ms}ms
                  </span>
                )}
              </div>
              <span
                className={`text-sm font-medium ${
                  isSuccess === true
                    ? "text-green-600"
                    : isSuccess === false
                      ? "text-red-600"
                      : "text-gray-400"
                }`}
              >
                {isSuccess === true
                  ? "success"
                  : isSuccess === false
                    ? "failed"
                    : "pending"}
              </span>
            </button>
            {expanded.has(call.id) && (
              <div className="border-t p-3 bg-gray-50 space-y-2">
                <div>
                  <span className="text-xs font-medium text-gray-500">
                    Input:
                  </span>
                  <pre className="text-xs mt-1 bg-white p-2 rounded overflow-x-auto">
                    {JSON.stringify(call.payload.arguments, null, 2)}
                  </pre>
                </div>
                {result && (
                  <div>
                    <span className="text-xs font-medium text-gray-500">
                      Output:
                    </span>
                    <pre className="text-xs mt-1 bg-white p-2 rounded overflow-x-auto">
                      {JSON.stringify(result.payload.output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {calls.length === 0 && (
        <p className="text-gray-400 text-center py-4">No tool calls yet.</p>
      )}
    </div>
  );
}
