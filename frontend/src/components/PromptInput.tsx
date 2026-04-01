"use client";

import { useState } from "react";

interface PromptInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
}

export function PromptInput({ onSubmit, disabled }: PromptInputProps) {
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    onSubmit(message.trim());
    setMessage("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", gap: "8px", marginTop: "16px" }}
    >
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Send a message to the agent..."
        disabled={disabled}
        style={{
          flex: 1,
          padding: "10px 12px",
          background: "#0a0a0a",
          border: "1px solid #222",
          borderRadius: "2px",
          color: "#e0e0e0",
          fontFamily: "inherit",
          fontSize: "14px",
          outline: "none",
          opacity: disabled ? 0.5 : 1,
        }}
        onFocus={(e) => (e.currentTarget.style.borderColor = "#00ff41")}
        onBlur={(e) => (e.currentTarget.style.borderColor = "#222")}
      />
      <button
        type="submit"
        disabled={disabled || !message.trim()}
        style={{
          padding: "10px 20px",
          background: "rgba(0, 255, 65, 0.1)",
          border: "1px solid rgba(0, 255, 65, 0.3)",
          borderRadius: "2px",
          color: "#00ff41",
          fontFamily: "inherit",
          fontSize: "14px",
          fontWeight: 700,
          letterSpacing: "1px",
          cursor: disabled || !message.trim() ? "not-allowed" : "pointer",
          opacity: disabled || !message.trim() ? 0.4 : 1,
        }}
      >
        SEND
      </button>
    </form>
  );
}
