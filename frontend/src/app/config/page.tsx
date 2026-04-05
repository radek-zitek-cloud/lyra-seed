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

// ── JSON syntax highlighting ─────────────────────────────

function highlightJson(text: string): React.ReactNode[] {
  // Tokenize JSON for syntax coloring
  const tokens: React.ReactNode[] = [];
  const re =
    /("(?:[^"\\]|\\.)*")\s*(:)|("(?:[^"\\]|\\.)*")|(true|false|null)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}[\],:])|(\s+)|(.)/g;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m[1] !== undefined) {
      // Key
      tokens.push(
        <span key={i++} style={{ color: "#6a8" }}>{m[1]}</span>,
        <span key={i++} style={{ color: "#888" }}>{m[2] ? ":" : ""}</span>,
      );
    } else if (m[3] !== undefined) {
      // String value
      tokens.push(<span key={i++} style={{ color: "#e8a" }}>{m[3]}</span>);
    } else if (m[4] !== undefined) {
      // Boolean / null
      tokens.push(<span key={i++} style={{ color: "#aa66ff" }}>{m[4]}</span>);
    } else if (m[5] !== undefined) {
      // Number
      tokens.push(<span key={i++} style={{ color: "#6688ff" }}>{m[5]}</span>);
    } else if (m[6] !== undefined) {
      // Punctuation
      tokens.push(<span key={i++} style={{ color: "#555" }}>{m[6]}</span>);
    } else {
      // Whitespace or other
      tokens.push(<span key={i++}>{m[0]}</span>);
    }
  }
  return tokens;
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
  mcp_servers: FileEntry[];
}

const CATEGORY_LABELS: Record<string, string> = {
  platform: "Platform Config",
  agent_configs: "Agent Configs",
  agent_prompts: "Agent Prompts",
  system_prompts: "System Prompts",
  skills: "Skills",
  mcp_servers: "MCP Servers",
};

const CREATABLE: Record<string, { dir: string; ext: string; template: string }> = {
  agent_configs: {
    dir: "prompts",
    ext: ".json",
    template: `{
  "model": null,
  "hitl_policy": "never",
  "temperature": 0.7,
  "max_iterations": 10
}
`,
  },
  agent_prompts: {
    dir: "prompts",
    ext: ".md",
    template: `# Agent Name

You are a helpful assistant.

## Capabilities

- Describe what this agent does

## Constraints

- Describe any constraints
`,
  },
  skills: {
    dir: "skills",
    ext: ".md",
    template: `---
name: skill-name
description: What this skill does
parameters:
  - name: input
    type: string
    required: true
    description: The input to process
---

Process the following input:

{{ input }}
`,
  },
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
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [serverAction, setServerAction] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [newFileCategory, setNewFileCategory] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");

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

  const createFile = useCallback(
    async (category: string, name: string) => {
      const spec = CREATABLE[category];
      if (!spec || !name.trim()) return;
      const cleanName = name.trim().replace(/[^a-zA-Z0-9_-]/g, "");
      if (!cleanName) return;
      const path = `${spec.dir}/${cleanName}${spec.ext}`;
      try {
        const res = await fetch(`${API}/config/file`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, content: spec.template }),
        });
        if (res.ok) {
          setNewFileCategory(null);
          setNewFileName("");
          // Refresh tree then open the new file
          const treeRes = await fetch(`${API}/config/files`);
          const newTree = await treeRes.json();
          setTree(newTree);
          loadFile(path);
        } else {
          const err = await res.json();
          setStatus(`Error: ${err.detail}`);
        }
      } catch {
        setStatus("Failed to create file");
      }
    },
    [loadFile],
  );

  // Guard file switch when there are unsaved changes
  const [pendingFile, setPendingFile] = useState<string | null>(null);

  const selectFile = useCallback(
    (path: string) => {
      if (path === selected) return;
      if (content !== original) {
        setPendingFile(path);
        return;
      }
      loadFile(path);
    },
    [selected, content, original, loadFile],
  );

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

  const doReload = useCallback(async () => {
    setServerAction("reloading");
    try {
      const res = await fetch(`${API}/config/reload`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setServerAction(`Reloaded: ${data.reloaded.join(", ")}`);
        // Refresh file tree
        fetch(`${API}/config/files`).then((r) => r.json()).then(setTree);
        setTimeout(() => setServerAction(null), 4000);
      } else {
        setServerAction("Reload failed");
        setTimeout(() => setServerAction(null), 3000);
      }
    } catch {
      setServerAction("Reload failed — server unreachable");
      setTimeout(() => setServerAction(null), 3000);
    }
  }, []);

  const doRestart = useCallback(async () => {
    setConfirmRestart(false);
    setServerAction("restarting");
    try {
      await fetch(`${API}/config/restart`, { method: "POST" });
      setServerAction("Server restarting — reconnecting...");
      // Poll until server is back
      const poll = setInterval(async () => {
        try {
          const res = await fetch(`${API}/health`);
          if (res.ok) {
            clearInterval(poll);
            setServerAction("Server restarted");
            fetch(`${API}/config/files`).then((r) => r.json()).then(setTree);
            setTimeout(() => setServerAction(null), 2000);
          }
        } catch {
          // Still restarting
        }
      }, 1000);
      // Give up after 30s
      setTimeout(() => clearInterval(poll), 30000);
    } catch {
      setServerAction("Restart failed");
      setTimeout(() => setServerAction(null), 3000);
    }
  }, []);

  const dirty = content !== original;
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Validate JSON on content change
  useEffect(() => {
    if (!selected?.endsWith(".json")) {
      setJsonError(null);
      return;
    }
    if (!content.trim()) {
      setJsonError(null);
      return;
    }
    try {
      JSON.parse(content);
      setJsonError(null);
    } catch (e) {
      setJsonError(e instanceof Error ? e.message : "Invalid JSON");
    }
  }, [content, selected]);

  // Warn on browser navigation / tab close with unsaved changes
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

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
          display: "flex",
          flexDirection: "column",
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
            if (files.length === 0 && !CREATABLE[key]) return null;
            return (
              <div key={key} style={{ marginBottom: 8 }}>
                <div
                  style={{
                    padding: "4px 12px",
                    fontSize: 10,
                    color: "#555",
                    letterSpacing: 1,
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  {label}
                  {CREATABLE[key] && (
                    <button
                      onClick={() => {
                        setNewFileCategory(newFileCategory === key ? null : key);
                        setNewFileName("");
                      }}
                      style={{
                        fontSize: 12,
                        background: "none",
                        border: "none",
                        color: newFileCategory === key ? "#e8a" : "#555",
                        cursor: "pointer",
                        padding: "0 2px",
                        fontFamily: "inherit",
                        lineHeight: 1,
                      }}
                    >
                      +
                    </button>
                  )}
                </div>
                {newFileCategory === key && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      createFile(key, newFileName);
                    }}
                    style={{
                      padding: "2px 12px 4px 20px",
                      display: "flex",
                      gap: 4,
                    }}
                  >
                    <input
                      autoFocus
                      value={newFileName}
                      onChange={(e) => setNewFileName(e.target.value)}
                      placeholder="name"
                      style={{
                        flex: 1,
                        fontSize: 11,
                        background: "#0a0a0a",
                        color: "#e0e0e0",
                        border: "1px solid #333",
                        borderRadius: 2,
                        padding: "2px 6px",
                        fontFamily: "inherit",
                        minWidth: 0,
                      }}
                    />
                    <button
                      type="submit"
                      disabled={!newFileName.trim()}
                      style={{
                        fontSize: 10,
                        padding: "2px 8px",
                        border: "1px solid #333",
                        borderRadius: 2,
                        background: newFileName.trim() ? "#2a4a2a" : "#1a1a1a",
                        color: newFileName.trim() ? "#8e8" : "#555",
                        cursor: newFileName.trim() ? "pointer" : "default",
                        fontFamily: "inherit",
                      }}
                    >
                      CREATE
                    </button>
                  </form>
                )}
                {files.map((f) => (
                  <div
                    key={f.path}
                    onClick={() => selectFile(f.path)}
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

        {/* Server actions */}
        <div
          style={{
            marginTop: "auto",
            padding: "12px",
            borderTop: "1px solid #222",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {serverAction && (
            <div
              style={{
                fontSize: 10,
                color: serverAction.startsWith("Reload failed") ||
                  serverAction.startsWith("Restart failed")
                  ? "#e66"
                  : "#6a8",
                padding: "4px 0",
                wordBreak: "break-word",
              }}
            >
              {serverAction}
            </div>
          )}
          <button
            onClick={doReload}
            disabled={serverAction === "reloading"}
            style={{
              fontSize: 11,
              padding: "5px 0",
              border: "1px solid #333",
              borderRadius: 2,
              background: "#1a1a2a",
              color: "#8af",
              cursor: "pointer",
              width: "100%",
            }}
          >
            RELOAD CONFIG
          </button>
          {!confirmRestart ? (
            <button
              onClick={() => setConfirmRestart(true)}
              disabled={serverAction === "restarting"}
              style={{
                fontSize: 11,
                padding: "5px 0",
                border: "1px solid #422",
                borderRadius: 2,
                background: "#1a1a1a",
                color: "#e88",
                cursor: "pointer",
                width: "100%",
              }}
            >
              RESTART SERVER
            </button>
          ) : (
            <div style={{ display: "flex", gap: 4 }}>
              <button
                onClick={doRestart}
                style={{
                  flex: 1,
                  fontSize: 11,
                  padding: "5px 0",
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
                onClick={() => setConfirmRestart(false)}
                style={{
                  flex: 1,
                  fontSize: 11,
                  padding: "5px 0",
                  border: "1px solid #333",
                  borderRadius: 2,
                  background: "#1a1a1a",
                  color: "#888",
                  cursor: "pointer",
                }}
              >
                CANCEL
              </button>
            </div>
          )}
          <div style={{ fontSize: 9, color: "#444", lineHeight: 1.3 }}>
            Reload applies skills and prompt changes.
            Restart required for MCP server or .env changes.
          </div>
        </div>
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

        {/* Editor */}
        {selected ? (
          <div style={{ flex: 1, position: "relative", minHeight: 0, overflow: "hidden" }}>
            {/* Syntax highlight layer (behind textarea) */}
            {selected.endsWith(".json") && (
              <pre
                aria-hidden
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  padding: 12,
                  margin: 0,
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  fontSize: 12,
                  lineHeight: 1.5,
                  tabSize: 2,
                  background: "#0a0a0a",
                  border: "none",
                  overflowY: "auto",
                  overflowX: "auto",
                  whiteSpace: "pre-wrap",
                  wordWrap: "break-word",
                  pointerEvents: "none",
                }}
              >
                {highlightJson(content)}
                {/* Extra line so scrolling matches textarea */}
                {"\n"}
              </pre>
            )}
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
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                padding: 12,
                margin: 0,
                border: "none",
                outline: "none",
                resize: "none",
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                fontSize: 12,
                lineHeight: 1.5,
                color: selected.endsWith(".json") ? "transparent" : "#d0d0d0",
                caretColor: "#d0d0d0",
                background: selected.endsWith(".json") ? "transparent" : "#0a0a0a",
                tabSize: 2,
              }}
              onScroll={(e) => {
                // Sync highlight layer scroll
                const pre = e.currentTarget.previousElementSibling as HTMLElement | null;
                if (pre) {
                  pre.scrollTop = e.currentTarget.scrollTop;
                  pre.scrollLeft = e.currentTarget.scrollLeft;
                }
              }}
            />
          </div>
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

        {/* JSON error bar */}
        {jsonError && selected?.endsWith(".json") && (
          <div
            style={{
              padding: "4px 12px",
              borderTop: "1px solid #422",
              fontSize: 11,
              color: "#e66",
              background: "#1a0a0a",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontWeight: 700 }}>JSON</span>
            {jsonError}
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

      {/* Unsaved changes dialog */}
      {pendingFile && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setPendingFile(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#111",
              border: "1px solid #333",
              borderRadius: 3,
              padding: "16px 20px",
              minWidth: 320,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div style={{ fontSize: 13, color: "#e0e0e0", fontWeight: 700 }}>
              Unsaved changes
            </div>
            <div style={{ fontSize: 12, color: "#888" }}>
              You have unsaved changes to{" "}
              <span style={{ color: "#e8a" }}>{selected?.split("/").pop()}</span>.
              What would you like to do?
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  save().then(() => {
                    setPendingFile(null);
                    loadFile(pendingFile);
                  });
                }}
                style={{
                  fontSize: 11,
                  padding: "5px 14px",
                  border: "1px solid #333",
                  borderRadius: 2,
                  background: "#2a4a2a",
                  color: "#8e8",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                SAVE
              </button>
              <button
                onClick={() => {
                  setPendingFile(null);
                  loadFile(pendingFile);
                }}
                style={{
                  fontSize: 11,
                  padding: "5px 14px",
                  border: "1px solid #422",
                  borderRadius: 2,
                  background: "#2a1a1a",
                  color: "#e88",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                DISCARD
              </button>
              <button
                onClick={() => setPendingFile(null)}
                style={{
                  fontSize: 11,
                  padding: "5px 14px",
                  border: "1px solid #333",
                  borderRadius: 2,
                  background: "#1a1a1a",
                  color: "#888",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                CANCEL
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
