"use client";

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

  const deleteFile = useCallback(async () => {
    if (!selected || !deletable) return;
    if (!confirm(`Delete ${selected}?`)) return;
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
        // Refresh file tree
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
                        selected === f.path
                          ? "#e0e0e0"
                          : "#888",
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
          {deletable && !dirty && (
            <button
              onClick={deleteFile}
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
        </div>

        {/* Text area */}
        {selected ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
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
      </div>
    </div>
  );
}
