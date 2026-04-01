"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AgentDetail } from "@/components/AgentDetail";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { HITLPanel } from "@/components/HITLPanel";
import { PromptInput } from "@/components/PromptInput";
import { ToolInspector } from "@/components/ToolInspector";
import { useEventStream } from "@/hooks/useEventStream";
import {
  fetchAgent,
  fetchAgentConversations,
  fetchAgentEvents,
  respondHITL,
  sendPrompt,
} from "@/lib/api";

export default function AgentPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Record<string, unknown> | null>(null);
  const [messages, setMessages] = useState<
    { role: string; content: string; timestamp?: string }[]
  >([]);
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [sending, setSending] = useState(false);
  const { events: liveEvents, connectionState } = useEventStream(agentId);

  useEffect(() => {
    fetchAgent(agentId).then(setAgent).catch(() => {});
    fetchAgentEvents(agentId).then(setEvents).catch(() => {});
    fetchAgentConversations(agentId)
      .then((convos: { messages: { role: string; content: string }[] }[]) => {
        if (convos.length > 0) setMessages(convos[0].messages);
      })
      .catch(() => {});
  }, [agentId]);

  // Merge live events
  useEffect(() => {
    if (liveEvents.length > 0) {
      setEvents((prev) => [...prev, ...liveEvents.slice(prev.length)]);
    }
  }, [liveEvents]);

  const handlePrompt = async (message: string) => {
    setSending(true);
    try {
      await sendPrompt(agentId, message);
      // Refresh data
      const [a, evts, convos] = await Promise.all([
        fetchAgent(agentId),
        fetchAgentEvents(agentId),
        fetchAgentConversations(agentId),
      ]);
      setAgent(a);
      setEvents(evts);
      if (convos.length > 0) setMessages(convos[0].messages);
    } finally {
      setSending(false);
    }
  };

  const handleHITLRespond = async (
    id: string,
    approved: boolean,
    message?: string,
  ) => {
    await respondHITL(id, approved, message);
    const updated = await fetchAgent(agentId);
    setAgent(updated);
  };

  if (!agent) {
    return <p className="text-gray-500">Loading agent...</p>;
  }

  const toolEvents = (events as Record<string, unknown>[]).filter(
    (e) => e.event_type === "tool_call" || e.event_type === "tool_result",
  );

  const hitlEvents = (events as Record<string, unknown>[]).filter(
    (e) =>
      e.event_type === "hitl_request" &&
      (agent as Record<string, unknown>).status === "waiting_hitl",
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <a href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Back to agents
        </a>
        <ConnectionStatus state={connectionState} />
      </div>

      <AgentDetail
        agent={agent as never}
        messages={messages as never}
        events={events as never}
      />

      <PromptInput onSubmit={handlePrompt} disabled={sending} />

      {hitlEvents.length > 0 && (
        <HITLPanel
          pendingActions={hitlEvents as never}
          onRespond={handleHITLRespond}
        />
      )}

      {toolEvents.length > 0 && (
        <ToolInspector toolEvents={toolEvents as never} />
      )}
    </div>
  );
}
