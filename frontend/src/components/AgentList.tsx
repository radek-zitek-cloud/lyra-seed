"use client";

interface Agent {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  idle: "bg-gray-200 text-gray-800",
  running: "bg-green-200 text-green-800",
  waiting_hitl: "bg-yellow-200 text-yellow-800",
  completed: "bg-blue-200 text-blue-800",
  failed: "bg-red-200 text-red-800",
};

export function AgentList({ agents }: { agents: Agent[] }) {
  return (
    <div className="space-y-3">
      {agents.map((agent) => (
        <a
          key={agent.id}
          href={`/agents/${agent.id}`}
          className="block border rounded-lg p-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-lg">{agent.name}</h3>
            <span
              className={`px-2 py-1 rounded text-sm font-medium ${STATUS_COLORS[agent.status] ?? "bg-gray-100"}`}
            >
              {agent.status}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Model: {String(agent.config?.model ?? "default")}
          </p>
        </a>
      ))}
      {agents.length === 0 && (
        <p className="text-gray-500 text-center py-8">No agents yet.</p>
      )}
    </div>
  );
}
