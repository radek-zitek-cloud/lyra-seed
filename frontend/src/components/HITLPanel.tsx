"use client";

import { useState } from "react";

interface HITLEvent {
  id: string;
  agent_id: string;
  event_type: string;
  module: string;
  timestamp: string;
  payload: {
    tool_name: string;
    arguments?: Record<string, unknown>;
  };
}

interface HITLPanelProps {
  pendingActions: HITLEvent[];
  onRespond: (agentId: string, approved: boolean, message?: string) => void;
}

export function HITLPanel({ pendingActions, onRespond }: HITLPanelProps) {
  const [messages, setMessages] = useState<Record<string, string>>({});

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-lg">Pending Approvals</h2>
      {pendingActions.map((action) => (
        <div key={action.id} className="border rounded-lg p-4 bg-yellow-50">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono font-medium">
              {action.payload.tool_name}
            </span>
            <span className="text-xs text-gray-500">
              Agent: {action.agent_id}
            </span>
          </div>
          {action.payload.arguments && (
            <pre className="text-xs bg-white p-2 rounded mb-3 overflow-x-auto">
              {JSON.stringify(action.payload.arguments, null, 2)}
            </pre>
          )}
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Optional message..."
              value={messages[action.id] ?? ""}
              onChange={(e) =>
                setMessages((prev) => ({ ...prev, [action.id]: e.target.value }))
              }
              className="flex-1 border rounded px-2 py-1 text-sm"
            />
            <button
              onClick={() =>
                onRespond(action.agent_id, true, messages[action.id])
              }
              className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
            >
              Approve
            </button>
            <button
              onClick={() =>
                onRespond(action.agent_id, false, messages[action.id])
              }
              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
            >
              Deny
            </button>
          </div>
        </div>
      ))}
      {pendingActions.length === 0 && (
        <p className="text-gray-400 text-center py-4">
          No pending approvals.
        </p>
      )}
    </div>
  );
}
