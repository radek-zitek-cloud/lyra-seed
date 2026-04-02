const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchAgents() {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}

export async function fetchAgent(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}`);
  if (!res.ok) throw new Error("Failed to fetch agent");
  return res.json();
}

export async function fetchAgentEvents(
  id: string,
  params?: { event_type?: string; module?: string },
) {
  const url = new URL(`${API_BASE}/agents/${id}/events`);
  if (params?.event_type) url.searchParams.set("event_type", params.event_type);
  if (params?.module) url.searchParams.set("module", params.module);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

export async function fetchAgentConversations(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function fetchTools() {
  const res = await fetch(`${API_BASE}/tools`);
  if (!res.ok) throw new Error("Failed to fetch tools");
  return res.json();
}

export async function fetchToolCalls(toolName: string) {
  const res = await fetch(`${API_BASE}/tools/${toolName}/calls`);
  if (!res.ok) throw new Error("Failed to fetch tool calls");
  return res.json();
}

export async function createAgent(name: string, config?: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, config: config ?? {} }),
  });
  if (!res.ok) throw new Error("Failed to create agent");
  return res.json();
}

export async function deleteAgent(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete agent");
  return res.json();
}

export async function sendPrompt(agentId: string, message: string) {
  const res = await fetch(`${API_BASE}/agents/${agentId}/prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Failed to send prompt");
  return res.json();
}

export async function respondHITL(
  agentId: string,
  approved: boolean,
  message?: string,
) {
  const res = await fetch(`${API_BASE}/agents/${agentId}/hitl-respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, message }),
  });
  if (!res.ok) throw new Error("Failed to respond to HITL");
  return res.json();
}

export async function fetchAgentChildren(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}/children`);
  if (!res.ok) throw new Error("Failed to fetch children");
  return res.json();
}

export async function fetchAgentMessages(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}/messages`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  return res.json();
}

export async function sendAgentMessage(
  agentId: string,
  content: string,
  messageType: string = "guidance",
) {
  const res = await fetch(`${API_BASE}/agents/${agentId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, message_type: messageType }),
  });
  if (!res.ok) throw new Error("Failed to send message");
  return res.json();
}

export async function fetchAgentCost(id: string) {
  const res = await fetch(`${API_BASE}/agents/${id}/cost`);
  if (!res.ok) throw new Error("Failed to fetch agent cost");
  return res.json();
}

export async function fetchMemories(params?: {
  agent_id?: string;
  memory_type?: string;
  q?: string;
  archived?: boolean;
  limit?: number;
}) {
  const url = new URL(`${API_BASE}/memories`);
  if (params?.agent_id) url.searchParams.set("agent_id", params.agent_id);
  if (params?.memory_type) url.searchParams.set("memory_type", params.memory_type);
  if (params?.q) url.searchParams.set("q", params.q);
  if (params?.archived !== undefined) url.searchParams.set("archived", String(params.archived));
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("Failed to fetch memories");
  return res.json();
}

export async function deleteMemory(id: string) {
  const res = await fetch(`${API_BASE}/memories/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete memory");
  return res.json();
}

export async function updateMemory(id: string, patch: { importance?: number; archived?: boolean }) {
  const res = await fetch(`${API_BASE}/memories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error("Failed to update memory");
  return res.json();
}

export function createEventStream(agentId?: string): EventSource {
  const url = agentId
    ? `${API_BASE}/agents/${agentId}/events/stream`
    : `${API_BASE}/events/stream`;
  return new EventSource(url);
}
