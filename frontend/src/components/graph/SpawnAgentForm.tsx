"use client";

import { useState } from "react";
import { createAgent } from "@/lib/api";

interface SpawnAgentFormProps {
  onCreated: () => void;
}

export function SpawnAgentForm({ onCreated }: SpawnAgentFormProps) {
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError("");
    try {
      const config: Record<string, unknown> = {};
      if (model.trim()) config.model = model.trim();
      await createAgent(name.trim(), undefined, config);
      setName("");
      setModel("");
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create agent");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      style={{
        padding: "12px",
        borderTop: "1px solid #1a1a1a",
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <div style={{ color: "#888", marginBottom: 8, fontSize: 9, letterSpacing: 1 }}>
        SPAWN AGENT
      </div>

      <input
        type="text"
        placeholder="Agent name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleCreate()}
        style={{
          width: "100%",
          background: "#0a0a0a",
          border: "1px solid #222",
          color: "#e0e0e0",
          padding: "4px 8px",
          borderRadius: 2,
          fontSize: 10,
          marginBottom: 6,
          fontFamily: "'JetBrains Mono', monospace",
          boxSizing: "border-box",
        }}
      />

      <input
        type="text"
        placeholder="Model (optional)"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        style={{
          width: "100%",
          background: "#0a0a0a",
          border: "1px solid #222",
          color: "#e0e0e0",
          padding: "4px 8px",
          borderRadius: 2,
          fontSize: 10,
          marginBottom: 6,
          fontFamily: "'JetBrains Mono', monospace",
          boxSizing: "border-box",
        }}
      />

      <button
        onClick={handleCreate}
        disabled={creating || !name.trim()}
        style={{
          width: "100%",
          background: creating ? "#333" : "#00ff41",
          color: "#000",
          border: "none",
          padding: "4px 8px",
          borderRadius: 2,
          fontSize: 10,
          cursor: creating ? "wait" : "pointer",
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 700,
        }}
      >
        {creating ? "CREATING..." : "CREATE"}
      </button>

      {error && (
        <div style={{ color: "#ff3333", marginTop: 4, fontSize: 9 }}>{error}</div>
      )}
    </div>
  );
}
