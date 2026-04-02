"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function fmtTime(ts?: string | null): string {
  if (!ts) return "";
  return new Date(ts).toISOString().slice(11, 19);
}

const TYPE_COLORS: Record<string, string> = {
  task: "#aa66ff",
  result: "#00ff41",
  question: "#6688ff",
  answer: "#4466dd",
  guidance: "#ffaa00",
  status_update: "#555",
};

const MESSAGE_TYPES = [
  "task",
  "result",
  "question",
  "answer",
  "guidance",
  "status_update",
];

interface Message {
  id: string;
  from_agent_id: string;
  to_agent_id: string;
  content: string;
  message_type: string;
  timestamp: string;
  in_reply_to: string | null;
}

function isNearBottom(el: HTMLElement, threshold = 30): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

export function MessagePanel({
  messages,
  currentAgentId,
  onSend,
}: {
  messages: Message[];
  currentAgentId: string;
  onSend: (content: string, messageType: string) => void;
}) {
  const [input, setInput] = useState("");
  const [msgType, setMsgType] = useState("guidance");
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) wasAtBottom.current = isNearBottom(el);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && wasAtBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim(), msgType);
    setInput("");
  };

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #1a1a1a",
        borderRadius: "3px",
        padding: "6px",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      <h2
        style={{
          fontSize: "11px",
          fontWeight: 700,
          color: "#888",
          letterSpacing: "1px",
          marginBottom: "4px",
          flexShrink: 0,
        }}
      >
        MESSAGES
        {messages.length > 0 && (
          <span style={{ color: "#555", fontWeight: 400, marginLeft: "6px" }}>
            {messages.length}
          </span>
        )}
      </h2>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          overflowY: "auto",
          minHeight: 0,
          maxHeight: "300px",
          marginBottom: "4px",
        }}
      >
        {messages.map((msg) => {
          const isSent = msg.from_agent_id === currentAgentId;
          const color = TYPE_COLORS[msg.message_type] ?? "#555";
          return (
            <div
              key={msg.id}
              style={{
                padding: "3px 6px",
                marginBottom: "2px",
                borderLeft: `2px solid ${color}`,
                background: "#0a0a0a",
                fontSize: "11px",
                lineHeight: "1.4",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: "6px",
                  marginBottom: "2px",
                }}
              >
                <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                  <span style={{ color: "#444", fontSize: "10px" }}>
                    {isSent ? "\u2192" : "\u2190"}
                  </span>
                  <span
                    style={{
                      color,
                      fontWeight: 700,
                      fontSize: "10px",
                      letterSpacing: "0.5px",
                    }}
                  >
                    {msg.message_type}
                  </span>
                  <span style={{ color: "#444", fontSize: "10px" }}>
                    {isSent ? `\u2192 ${msg.to_agent_id.slice(0, 8)}` : `\u2190 ${msg.from_agent_id.slice(0, 8)}`}
                  </span>
                </div>
                <span style={{ color: "#333", fontSize: "10px", flexShrink: 0 }}>
                  {fmtTime(msg.timestamp)}
                </span>
              </div>
              <div style={{ color: "#d0d0d0", whiteSpace: "pre-wrap" }}>
                {msg.content}
              </div>
            </div>
          );
        })}
        {messages.length === 0 && (
          <div
            style={{
              color: "#555",
              textAlign: "center",
              padding: "12px",
              fontSize: "11px",
            }}
          >
            No messages.
          </div>
        )}
      </div>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: "4px", flexShrink: 0 }}
      >
        <select
          value={msgType}
          onChange={(e) => setMsgType(e.target.value)}
          style={{
            padding: "2px 4px",
            background: "#0a0a0a",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#b0b0b0",
            fontFamily: "inherit",
            fontSize: "10px",
            outline: "none",
          }}
        >
          {MESSAGE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Send message..."
          style={{
            flex: 1,
            padding: "2px 6px",
            background: "#0a0a0a",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#e0e0e0",
            fontFamily: "inherit",
            fontSize: "11px",
            outline: "none",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "#00ff41")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "#222")}
        />
        <button
          type="submit"
          disabled={!input.trim()}
          aria-label="Send"
          style={{
            padding: "2px 8px",
            background: "rgba(0, 255, 65, 0.1)",
            border: "1px solid rgba(0, 255, 65, 0.3)",
            borderRadius: "2px",
            color: "#00ff41",
            fontFamily: "inherit",
            fontSize: "10px",
            fontWeight: 700,
            cursor: input.trim() ? "pointer" : "not-allowed",
            opacity: input.trim() ? 1 : 0.4,
          }}
        >
          SEND
        </button>
      </form>
    </div>
  );
}
