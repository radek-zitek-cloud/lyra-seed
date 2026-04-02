"use client";

import { useEffect, useRef, useState } from "react";

interface PromptInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
}

export function PromptInput({ onSubmit, disabled }: PromptInputProps) {
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const prevDisabled = useRef(disabled);
  useEffect(() => {
    if (prevDisabled.current && !disabled) {
      inputRef.current?.focus();
    }
    prevDisabled.current = disabled;
  }, [disabled]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    onSubmit(message.trim());
    setMessage("");
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", gap: "4px" }}
    >
      <input
        ref={inputRef}
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Send a message to the agent..."
        disabled={disabled}
        style={{
          flex: 1,
          padding: "4px 8px",
          background: "#0a0a0a",
          border: "1px solid #222",
          borderRadius: "2px",
          color: "#e0e0e0",
          fontFamily: "inherit",
          fontSize: "12px",
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
          padding: "4px 12px",
          background: disabled
            ? "rgba(255, 170, 0, 0.1)"
            : "rgba(0, 255, 65, 0.1)",
          border: `1px solid ${disabled ? "rgba(255, 170, 0, 0.3)" : "rgba(0, 255, 65, 0.3)"}`,
          borderRadius: "2px",
          color: disabled ? "#ffaa00" : "#00ff41",
          fontFamily: "inherit",
          fontSize: "11px",
          fontWeight: 700,
          letterSpacing: "1px",
          cursor: disabled || !message.trim() ? "not-allowed" : "pointer",
          opacity: disabled && !message.trim() ? 0.4 : 1,
          animation: disabled ? "pulse-glow 1.5s ease-in-out infinite" : "none",
        }}
      >
        {disabled ? "PROCESSING" : "SEND"}
      </button>
    </form>
  );
}
