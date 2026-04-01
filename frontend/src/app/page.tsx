"use client";

import { useEffect, useState } from "react";

import { AgentList } from "@/components/AgentList";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { useEventStream } from "@/hooks/useEventStream";
import { createAgent, fetchAgents } from "@/lib/api";

export default function HomePage() {
  const [agents, setAgents] = useState<
    {
      id: string;
      name: string;
      status: string;
      config: Record<string, unknown>;
      created_at: string;
      updated_at: string;
    }[]
  >([]);
  const [newName, setNewName] = useState("");
  const { connectionState } = useEventStream();

  useEffect(() => {
    fetchAgents()
      .then(setAgents)
      .catch(() => {});
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await createAgent(newName.trim());
    setNewName("");
    const updated = await fetchAgents();
    setAgents(updated);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agents</h1>
        <ConnectionStatus state={connectionState} />
      </div>

      <form onSubmit={handleCreate} className="flex gap-2">
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New agent name..."
          className="border rounded-lg px-4 py-2 flex-1"
        />
        <button
          type="submit"
          disabled={!newName.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          Create Agent
        </button>
      </form>

      <AgentList agents={agents} />
    </div>
  );
}
