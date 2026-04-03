"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Help dictionary ──────────────────────────────────────

const HELP: Record<string, string> = {
  // .env
  LYRA_OPENROUTER_API_KEY: "OpenRouter API key for LLM and embedding calls (required)",
  LYRA_HOST: "Backend server bind address (default: 0.0.0.0)",
  LYRA_PORT: "Backend server bind port (default: 8000)",
  // lyra.config.json — top level
  dataDir: "Directory for SQLite databases and memory storage (default: ./data)",
  systemPromptsDir: "Directory containing agent prompt and config files (default: ./prompts)",
  skillsDir: "Directory containing skill .md files (default: ./skills)",
  defaultModel: "Default LLM model for agent reasoning",
  embeddingModel: "Model for memory embeddings",
  summaryModel: "Model for context compression summaries (cheaper model recommended)",
  extractionModel: "Model for automatic fact extraction (cheaper model recommended)",
  orchestrationModel: "Model for orchestration LLM calls — decomposition, subtask execution, synthesis. Falls back to agent's own model if not set",
  maxSubtasks: "Maximum subtasks the decomposer can produce per orchestration call (default: 10)",
  mcpServers: "MCP server definitions. Each entry defines a server providing tools to agents",
  modelCosts: "Per-model costs as [input_per_Mtok, output_per_Mtok] in USD for cost tracking",
  defaultModelCost: "Fallback cost for models not in modelCosts (default: [1.0, 4.0])",
  orchestrationTemperature: "Temperature for orchestration LLM calls (default: 0.3)",
  mcpRequestTimeout: "Timeout in seconds for MCP server requests (default: 30)",
  maxSpawnDepth: "Maximum sub-agent spawn depth to prevent runaway recursion (default: 3)",
  // lyra.config.json — retry
  "retry": "LLM API retry configuration",
  "retry.max_retries": "Maximum retry attempts (default: 3)",
  "retry.base_delay": "Base delay in seconds for exponential backoff (default: 1.0)",
  "retry.max_delay": "Maximum delay between retries in seconds (default: 30.0)",
  "retry.timeout": "Per-request timeout in seconds (default: 60.0)",
  // lyra.config.json — hitl
  "hitl": "Human-in-the-loop gate configuration",
  "hitl.timeout_seconds": "How long an agent waits for human approval before timing out (default: 300)",
  // lyra.config.json — memoryGC
  "memoryGC": "Memory garbage collection configuration",
  "memoryGC.prune_threshold": "Decay score below which memories are pruned (default: 0.1)",
  "memoryGC.max_entries": "Maximum memories per agent before pruning (default: 500)",
  "memoryGC.dedup_threshold": "Similarity threshold for memory deduplication, 0.0-1.0 (default: 0.9)",
  "memoryGC.half_life_days": "Half-life for memory decay in days (default: 7.0)",
  "memoryGC.decay_weights": "Weights for decay scoring [recency, importance, access_count] (default: [0.6, 0.2, 0.2])",
  // lyra.config.json — context
  "context": "Context compression configuration",
  "context.max_tokens": "Maximum context tokens before compression kicks in (default: 100000)",
  "context.memory_top_k": "Number of relevant memories to inject per turn (default: 5)",
  // agent .json — fields
  model: "LLM model for this agent's reasoning (inherits from defaultModel if not set)",
  temperature: "LLM temperature — higher = more creative, lower = more precise (default: 0.7)",
  max_iterations: "Maximum tool-call loop iterations per prompt (default: 10)",
  hitl_policy: "HITL approval policy: 'always_ask', 'dangerous_only', or 'never' (default: never)",
  auto_extract: "Automatically extract facts from conversations to memory (default: true)",
  summary_model: "Model for context compression (inherits from platform summaryModel)",
  extraction_model: "Model for fact extraction (inherits from platform extractionModel)",
  orchestration_model: "Model for orchestration LLM calls (inherits from platform orchestrationModel)",
  max_subtasks: "Maximum subtasks per orchestration call (inherits from platform maxSubtasks)",
  allowed_mcp_servers: "Which MCP servers this agent can access. null = all, [] = none, ['filesystem'] = only filesystem",
  allowed_tools: "Explicit tool name whitelist. [] = no restriction. When set, only listed tools are visible",
  memory_sharing: "Default visibility per memory type. Values: 'public', 'private', 'team'",
  // skill frontmatter
  name: "Skill name — used as the tool name agents call",
  description: "What the skill does — shown to the LLM in the tool list",
  parameters: "Skill parameters — each becomes a tool argument",
  required: "Whether this parameter is required (true/false)",
  type: "Parameter type (string, number, boolean)",
};

// ── Key resolution from cursor position ──────────────────

function getKeyAtCursor(text: string, cursorPos: number, filePath: string): string | null {
  if (filePath.endsWith(".env") || filePath === ".env") {
    return getEnvKey(text, cursorPos);
  }
  if (filePath.endsWith(".json")) {
    return getJsonKey(text, cursorPos);
  }
  if (filePath.endsWith(".md") && text.startsWith("---")) {
    return getYamlKey(text, cursorPos);
  }
  return null;
}

function getEnvKey(text: string, pos: number): string | null {
  const line = getLineAt(text, pos);
  const m = line.match(/^([A-Z_]+)\s*=/);
  return m ? m[1] : null;
}

function getJsonKey(text: string, pos: number): string | null {
  const lines = text.substring(0, pos).split("\n");
  const currentLine = getLineAt(text, pos);

  // Extract key from current line
  const keyMatch = currentLine.match(/^\s*"([^"]+)"\s*:/);
  if (!keyMatch) return null;

  const key = keyMatch[1];
  const indent = currentLine.search(/\S/);

  // If top-level (indent <= 2), return key directly
  if (indent <= 2) return key;

  // Walk backward to find parent key
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    const lineIndent = line.search(/\S/);
    if (lineIndent < 0) continue;
    if (lineIndent < indent) {
      const parentMatch = line.match(/^\s*"([^"]+)"\s*:/);
      if (parentMatch) {
        return `${parentMatch[1]}.${key}`;
      }
      break;
    }
  }

  return key;
}

function getYamlKey(text: string, pos: number): string | null {
  const line = getLineAt(text, pos);
  // Inside frontmatter
  const m = line.match(/^\s*(\w+)\s*:/);
  return m ? m[1] : null;
}

function getLineAt(text: string, pos: number): string {
  const start = text.lastIndexOf("\n", pos - 1) + 1;
  let end = text.indexOf("\n", pos);
  if (end === -1) end = text.length;
  return text.substring(start, end);
}

// ── Component ────────────────────────────────────────────

interface FileEntry {
  name: string;
  path: string;
  size: number;
}

interface FileTree {
  platform: FileEntry[];
  agent_configs: FileEntry[];
  agent_prompts: FileEntry[];
  system_prompts: FileEntry[];
  skills: FileEntry[];
}

const CATEGORY_LABELS: Record<string, string> = {
  platform: "Platform Config",
  agent_configs: "Agent Configs",
  agent_prompts: "Agent Prompts",
  system_prompts: "System Prompts",
  skills: "Skills",
};

export default function ConfigPage() {
  const [tree, setTree] = useState<FileTree | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [helpText, setHelpText] = useState<string | null>(null);
  const [helpKey, setHelpKey] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load file tree
  useEffect(() => {
    fetch(`${API}/config/files`)
      .then((r) => r.json())
      .then(setTree)
      .catch(() => setStatus("Failed to load file list"));
  }, []);

  // Load file content
  const loadFile = useCallback((path: string) => {
    setSelected(path);
    setStatus(null);
    setHelpText(null);
    setHelpKey(null);
    setConfirmDelete(false);
    fetch(`${API}/config/file?path=${encodeURIComponent(path)}`)
      .then((r) => r.json())
      .then((d) => {
        setContent(d.content);
        setOriginal(d.content);
      })
      .catch(() => setStatus("Failed to load file"));
  }, []);

  // Save file
  const save = useCallback(async () => {
    if (!selected) return;
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/config/file`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: selected, content }),
      });
      if (res.ok) {
        setOriginal(content);
        setStatus("Saved");
        setTimeout(() => setStatus(null), 2000);
      } else {
        const err = await res.json();
        setStatus(`Error: ${err.detail}`);
      }
    } catch {
      setStatus("Failed to save");
    }
    setSaving(false);
  }, [selected, content]);

  const cancel = useCallback(() => {
    setContent(original);
    setStatus(null);
  }, [original]);

  const deletable =
    selected &&
    !selected.startsWith("lyra.config") &&
    !selected.startsWith(".env") &&
    !selected.startsWith("prompts/system/");

  const doDelete = useCallback(async () => {
    if (!selected || !deletable) return;
    setConfirmDelete(false);
    setStatus(null);
    try {
      const res = await fetch(
        `${API}/config/file?path=${encodeURIComponent(selected)}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        setSelected(null);
        setContent("");
        setOriginal("");
        setStatus("Deleted");
        fetch(`${API}/config/files`)
          .then((r) => r.json())
          .then(setTree);
        setTimeout(() => setStatus(null), 2000);
      } else {
        const err = await res.json();
        setStatus(`Error: ${err.detail}`);
      }
    } catch {
      setStatus("Failed to delete");
    }
  }, [selected, deletable]);

  // Cursor tracking for context help
  const updateHelp = useCallback(() => {
    if (!selected || !textareaRef.current) return;
    const pos = textareaRef.current.selectionStart;
    const key = getKeyAtCursor(content, pos, selected);
    setHelpKey(key);
    setHelpText(key ? HELP[key] || null : null);
  }, [selected, content]);

  const dirty = content !== original;

  return (
    <div style={{ display: "flex", height: "100%", gap: 0 }}>
      {/* Sidebar */}
      <div
        style={{
          width: 280,
          flexShrink: 0,
          borderRight: "1px solid #222",
          overflowY: "auto",
          padding: "8px 0",
        }}
      >
        <div
          style={{
            padding: "4px 12px 8px",
            fontSize: 11,
            color: "#666",
            letterSpacing: 1,
          }}
        >
          CONFIGURATION FILES
        </div>
        {tree &&
          Object.entries(CATEGORY_LABELS).map(([key, label]) => {
            const files = tree[key as keyof FileTree] || [];
            if (files.length === 0) return null;
            return (
              <div key={key} style={{ marginBottom: 8 }}>
                <div
                  style={{
                    padding: "4px 12px",
                    fontSize: 10,
                    color: "#555",
                    letterSpacing: 1,
                    textTransform: "uppercase",
                  }}
                >
                  {label}
                </div>
                {files.map((f) => (
                  <div
                    key={f.path}
                    onClick={() => loadFile(f.path)}
                    style={{
                      padding: "3px 12px 3px 20px",
                      fontSize: 12,
                      cursor: "pointer",
                      color:
                        selected === f.path ? "#e0e0e0" : "#888",
                      background:
                        selected === f.path
                          ? "#1a1a2e"
                          : "transparent",
                      borderLeft:
                        selected === f.path
                          ? "2px solid #4a6"
                          : "2px solid transparent",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {f.name}
                    <span
                      style={{
                        color: "#444",
                        fontSize: 10,
                        marginLeft: 6,
                      }}
                    >
                      {f.size > 1024
                        ? `${(f.size / 1024).toFixed(1)}k`
                        : `${f.size}b`}
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
      </div>

      {/* Editor */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {/* Toolbar */}
        <div
          style={{
            padding: "6px 12px",
            borderBottom: "1px solid #222",
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
          }}
        >
          <span
            style={{ fontSize: 12, color: "#888", flex: 1 }}
          >
            {selected || "Select a file"}
            {dirty && (
              <span style={{ color: "#e8a", marginLeft: 8 }}>
                (modified)
              </span>
            )}
          </span>
          {status && (
            <span
              style={{
                fontSize: 11,
                color: status.startsWith("Error")
                  ? "#e66"
                  : "#6e6",
              }}
            >
              {status}
            </span>
          )}
          {dirty && (
            <button
              onClick={cancel}
              style={{
                fontSize: 11,
                padding: "3px 12px",
                border: "1px solid #333",
                borderRadius: 2,
                background: "#1a1a1a",
                color: "#e8a",
                cursor: "pointer",
              }}
            >
              CANCEL
            </button>
          )}
          <button
            onClick={save}
            disabled={!dirty || saving}
            style={{
              fontSize: 11,
              padding: "3px 12px",
              border: "1px solid #333",
              borderRadius: 2,
              background:
                dirty && !saving ? "#2a4a2a" : "#1a1a1a",
              color:
                dirty && !saving ? "#8e8" : "#555",
              cursor:
                dirty && !saving ? "pointer" : "default",
            }}
          >
            {saving ? "SAVING..." : "SAVE"}
          </button>
          {deletable && !dirty && !confirmDelete && (
            <button
              onClick={() => setConfirmDelete(true)}
              style={{
                fontSize: 11,
                padding: "3px 12px",
                border: "1px solid #422",
                borderRadius: 2,
                background: "#1a1a1a",
                color: "#e66",
                cursor: "pointer",
              }}
            >
              DELETE
            </button>
          )}
          {confirmDelete && (
            <>
              <span style={{ fontSize: 11, color: "#e66" }}>
                Delete {selected?.split("/").pop()}?
              </span>
              <button
                onClick={doDelete}
                style={{
                  fontSize: 11,
                  padding: "3px 12px",
                  border: "1px solid #622",
                  borderRadius: 2,
                  background: "#3a1a1a",
                  color: "#f88",
                  cursor: "pointer",
                }}
              >
                CONFIRM
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                style={{
                  fontSize: 11,
                  padding: "3px 12px",
                  border: "1px solid #333",
                  borderRadius: 2,
                  background: "#1a1a1a",
                  color: "#888",
                  cursor: "pointer",
                }}
              >
                CANCEL
              </button>
            </>
          )}
        </div>

        {/* Text area */}
        {selected ? (
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setTimeout(updateHelp, 0);
            }}
            onClick={updateHelp}
            onKeyUp={updateHelp}
            spellCheck={false}
            style={{
              flex: 1,
              width: "100%",
              padding: 12,
              margin: 0,
              border: "none",
              outline: "none",
              resize: "none",
              fontFamily:
                "'JetBrains Mono', 'Fira Code', monospace",
              fontSize: 12,
              lineHeight: 1.5,
              color: "#d0d0d0",
              background: "#0a0a0a",
              tabSize: 2,
            }}
          />
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#444",
              fontSize: 13,
            }}
          >
            Select a file from the sidebar to view and edit
          </div>
        )}

        {/* Context help bar */}
        {selected && (
          <div
            style={{
              padding: "5px 12px",
              borderTop: "1px solid #222",
              fontSize: 11,
              color: helpText ? "#aaa" : "#444",
              background: "#0d0d0d",
              flexShrink: 0,
              minHeight: 24,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {helpKey && (
              <span style={{ color: "#6a8", fontFamily: "monospace" }}>
                {helpKey}
              </span>
            )}
            {helpText ? (
              <span>{helpText}</span>
            ) : helpKey ? (
              <span style={{ color: "#555", fontStyle: "italic" }}>
                No description available
              </span>
            ) : (
              <span>Place cursor on a config key for help</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
