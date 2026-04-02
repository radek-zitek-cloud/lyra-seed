"use client";

import { useEffect, useState } from "react";

import { deleteMemory, fetchMemories, updateMemory } from "@/lib/api";

const TYPE_COLORS: Record<string, string> = {
  fact: "#00ff41",
  preference: "#6688ff",
  decision: "#ffaa00",
  outcome: "#cc8800",
  procedure: "#aa66ff",
  tool_knowledge: "#00ccff",
  domain_knowledge: "#0099cc",
  episodic: "#555",
};

const MEMORY_TYPES = [
  "fact",
  "preference",
  "decision",
  "outcome",
  "procedure",
  "tool_knowledge",
  "domain_knowledge",
  "episodic",
];

interface Memory {
  id: string;
  agent_id: string;
  content: string;
  memory_type: string;
  importance: number;
  visibility: string;
  created_at: string;
  last_accessed_at: string;
  access_count: number;
  decay_score: number;
  archived: boolean;
}

function fmtDate(ts: string): string {
  return new Date(ts).toISOString().slice(0, 19).replace("T", " ");
}

export default function MemoriesPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [archivedFilter, setArchivedFilter] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = async () => {
    const params: Record<string, unknown> = { limit: 100 };
    if (search.trim()) params.q = search.trim();
    if (typeFilter) params.memory_type = typeFilter;
    if (archivedFilter === "true") params.archived = true;
    if (archivedFilter === "false") params.archived = false;
    const data = await fetchMemories(params as never);
    setMemories(data);
  };

  useEffect(() => {
    load().catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load().catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteMemory(id);
    await load();
  };

  const handleToggleArchive = async (m: Memory) => {
    await updateMemory(m.id, { archived: !m.archived });
    await load();
  };

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <h1
          style={{
            fontSize: "14px",
            fontWeight: 700,
            color: "#888",
            letterSpacing: "1px",
          }}
        >
          MEMORIES
          <span style={{ color: "#555", fontWeight: 400, marginLeft: "8px" }}>
            {memories.length}
          </span>
        </h1>
      </div>

      {/* Search + Filters */}
      <form
        onSubmit={handleSearch}
        style={{
          display: "flex",
          gap: "6px",
          marginBottom: "16px",
          flexWrap: "wrap",
        }}
      >
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Semantic search..."
          style={{
            flex: 1,
            minWidth: "200px",
            padding: "4px 8px",
            background: "#0a0a0a",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#e0e0e0",
            fontFamily: "inherit",
            fontSize: "12px",
            outline: "none",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "#00ff41")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "#222")}
        />
        <select
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setTimeout(() => load(), 0);
          }}
          style={{
            padding: "4px 8px",
            background: "#111",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#b0b0b0",
            fontFamily: "inherit",
            fontSize: "11px",
            outline: "none",
          }}
        >
          <option value="">ALL TYPES</option>
          {MEMORY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.toUpperCase()}
            </option>
          ))}
        </select>
        <select
          value={archivedFilter}
          onChange={(e) => {
            setArchivedFilter(e.target.value);
            setTimeout(() => load(), 0);
          }}
          style={{
            padding: "4px 8px",
            background: "#111",
            border: "1px solid #222",
            borderRadius: "2px",
            color: "#b0b0b0",
            fontFamily: "inherit",
            fontSize: "11px",
            outline: "none",
          }}
        >
          <option value="">ALL STATUS</option>
          <option value="false">ACTIVE</option>
          <option value="true">ARCHIVED</option>
        </select>
        <button
          type="submit"
          style={{
            padding: "4px 12px",
            background: "rgba(0, 255, 65, 0.1)",
            border: "1px solid rgba(0, 255, 65, 0.3)",
            borderRadius: "2px",
            color: "#00ff41",
            fontFamily: "inherit",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "1px",
            cursor: "pointer",
          }}
        >
          SEARCH
        </button>
      </form>

      {/* Memory List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {memories.map((m) => {
          const color = TYPE_COLORS[m.memory_type] ?? "#555";
          const isExpanded = expanded.has(m.id);
          return (
            <div
              key={m.id}
              style={{
                background: "#111",
                border: "1px solid #1a1a1a",
                borderLeft: `3px solid ${color}`,
                borderRadius: "3px",
                opacity: m.archived ? 0.5 : 1,
              }}
            >
              <button
                onClick={() => toggle(m.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  width: "100%",
                  padding: "6px 10px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "inherit",
                  fontSize: "12px",
                  color: "#b0b0b0",
                  gap: "8px",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "#0a0a0a")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "none")
                }
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <span style={{ color: "#444", fontSize: "10px" }}>
                    {isExpanded ? "\u25BC" : "\u25B6"}
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      color,
                      letterSpacing: "0.5px",
                      flexShrink: 0,
                    }}
                  >
                    {m.memory_type}
                  </span>
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: "#d0d0d0",
                    }}
                  >
                    {m.content}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    flexShrink: 0,
                    fontSize: "10px",
                  }}
                >
                  {m.archived && (
                    <span style={{ color: "#ff3333" }}>ARCHIVED</span>
                  )}
                  <span style={{ color: "#555" }}>
                    imp:{m.importance.toFixed(1)}
                  </span>
                  <span style={{ color: "#444" }}>
                    decay:{m.decay_score.toFixed(2)}
                  </span>
                  <span style={{ color: "#333" }}>{m.visibility}</span>
                </div>
              </button>
              {isExpanded && (
                <div
                  style={{
                    padding: "0 10px 8px",
                    fontSize: "11px",
                  }}
                >
                  <div
                    style={{
                      background: "#0a0a0a",
                      border: "1px solid #1a1a1a",
                      borderRadius: "2px",
                      padding: "8px",
                      marginBottom: "8px",
                      color: "#d0d0d0",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {m.content}
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 1fr",
                      gap: "4px 12px",
                      fontSize: "10px",
                      color: "#555",
                      marginBottom: "8px",
                    }}
                  >
                    <span>Agent: {m.agent_id.slice(0, 8)}...</span>
                    <span>Created: {fmtDate(m.created_at)}</span>
                    <span>Accessed: {fmtDate(m.last_accessed_at)}</span>
                    <span>Access count: {m.access_count}</span>
                    <span>Importance: {m.importance}</span>
                    <span>Decay: {m.decay_score.toFixed(4)}</span>
                  </div>
                  <div style={{ display: "flex", gap: "6px" }}>
                    <button
                      onClick={() => handleToggleArchive(m)}
                      style={{
                        padding: "2px 8px",
                        background: "none",
                        border: "1px solid #222",
                        borderRadius: "2px",
                        color: "#555",
                        fontFamily: "inherit",
                        fontSize: "10px",
                        cursor: "pointer",
                      }}
                    >
                      {m.archived ? "UNARCHIVE" : "ARCHIVE"}
                    </button>
                    <button
                      onClick={() => handleDelete(m.id)}
                      style={{
                        padding: "2px 8px",
                        background: "none",
                        border: "1px solid #222",
                        borderRadius: "2px",
                        color: "#555",
                        fontFamily: "inherit",
                        fontSize: "10px",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = "#ff3333";
                        e.currentTarget.style.borderColor = "#ff3333";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = "#555";
                        e.currentTarget.style.borderColor = "#222";
                      }}
                    >
                      DELETE
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {memories.length === 0 && (
          <div
            style={{
              color: "#333",
              textAlign: "center",
              padding: "32px",
              fontSize: "12px",
            }}
          >
            No memories found.
          </div>
        )}
      </div>
    </div>
  );
}
