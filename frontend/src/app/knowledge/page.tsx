"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchKnowledgeChunks, fetchKnowledgeSources, searchKnowledge } from "@/lib/api";

interface KnowledgeSource {
  source: string;
  chunk_count: number;
}

interface KnowledgeChunk {
  source: string;
  heading_path: string;
  content: string;
  directory: string;
}

const NO_PATH = "NO-PATH";

/** Build a tree: directory -> source -> chunks */
interface SourceNode {
  source: string;
  chunks: KnowledgeChunk[];
}

interface DirNode {
  /** Display label for this directory level */
  label: string;
  /** Full path key */
  path: string;
  /** Files directly in this directory */
  sources: SourceNode[];
  /** Subdirectories */
  children: DirNode[];
}

function buildTree(chunks: KnowledgeChunk[]): DirNode[] {
  // Group: directory -> source -> chunks
  const dirMap = new Map<string, Map<string, KnowledgeChunk[]>>();
  for (const chunk of chunks) {
    const dir = chunk.directory || NO_PATH;
    if (!dirMap.has(dir)) dirMap.set(dir, new Map());
    const srcMap = dirMap.get(dir)!;
    if (!srcMap.has(chunk.source)) srcMap.set(chunk.source, []);
    srcMap.get(chunk.source)!.push(chunk);
  }

  // Find common prefix among all real paths (not NO_PATH) to shorten display
  const realPaths = Array.from(dirMap.keys()).filter((d) => d !== NO_PATH);
  let commonPrefix = "";
  if (realPaths.length > 0) {
    const parts0 = realPaths[0].split("/");
    for (let i = 0; i < parts0.length; i++) {
      const prefix = parts0.slice(0, i + 1).join("/");
      if (realPaths.every((p) => p.startsWith(prefix + "/") || p === prefix)) {
        commonPrefix = prefix;
      } else break;
    }
  }

  // Build nested tree from flat directory paths
  const root: DirNode = { label: "", path: "", sources: [], children: [] };

  for (const [dir, srcMap] of Array.from(dirMap.entries()).sort(([a], [b]) => a.localeCompare(b))) {
    const sources: SourceNode[] = Array.from(srcMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([source, chunks]) => ({ source, chunks }));

    if (dir === NO_PATH) {
      root.children.unshift({
        label: NO_PATH,
        path: NO_PATH,
        sources,
        children: [],
      });
      continue;
    }

    // Strip common prefix for display
    const relPath = commonPrefix && dir.startsWith(commonPrefix)
      ? dir.slice(commonPrefix.length + 1) || dir.split("/").pop() || dir
      : dir;

    // Split into segments and nest
    const segments = relPath.split("/").filter(Boolean);
    let current = root;
    let builtPath = commonPrefix;

    for (let i = 0; i < segments.length; i++) {
      builtPath = builtPath ? `${builtPath}/${segments[i]}` : segments[i];
      let child = current.children.find((c) => c.label === segments[i]);
      if (!child) {
        child = { label: segments[i], path: builtPath, sources: [], children: [] };
        current.children.push(child);
      }
      current = child;
    }
    current.sources.push(...sources);
  }

  // If there's only a single top-level dir with no sources, flatten it
  if (root.children.length === 1 && root.sources.length === 0) {
    return root.children;
  }
  if (root.sources.length > 0) return [root];
  return root.children;
}

function ChunkRow({
  chunk,
  index,
  expanded,
  onToggle,
}: {
  chunk: KnowledgeChunk;
  index: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ borderLeft: "2px solid #00cc33", marginBottom: "1px" }}>
      <button
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          padding: "2px 4px",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "inherit",
          fontSize: "11px",
          color: "#b0b0b0",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#0a0a0a")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "4px", minWidth: 0, flex: 1 }}>
          <span style={{ color: "#777", fontSize: "9px" }}>
            {expanded ? "\u25BC" : "\u25B6"}
          </span>
          {chunk.heading_path && (
            <span style={{ color: "#666", fontSize: "10px", flexShrink: 0 }}>
              {chunk.heading_path}
            </span>
          )}
          <span style={{ color: "#999", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {chunk.content.slice(0, 120)}
          </span>
        </div>
        <span style={{ color: "#555", fontSize: "10px", flexShrink: 0 }}>
          {chunk.content.length} chars
        </span>
      </button>
      {expanded && (
        <div style={{ padding: "0 4px 4px" }}>
          <pre
            style={{
              fontSize: "10px",
              color: "#b0b0b0",
              background: "#0a0a0a",
              border: "1px solid #1a1a1a",
              borderRadius: "2px",
              padding: "4px",
              overflowX: "auto",
              whiteSpace: "pre-wrap",
              maxHeight: "300px",
              overflowY: "auto",
              margin: 0,
            }}
          >
            {chunk.content}
          </pre>
        </div>
      )}
    </div>
  );
}

function DirTreeNode({
  node,
  depth,
  expandedChunks,
  toggleChunk,
  collapsedNodes,
  toggleNode,
  expandedSources,
  toggleSource,
}: {
  node: DirNode;
  depth: number;
  expandedChunks: Set<string>;
  toggleChunk: (key: string) => void;
  collapsedNodes: Set<string>;
  toggleNode: (key: string) => void;
  expandedSources: Set<string>;
  toggleSource: (key: string) => void;
}) {
  const isCollapsed = collapsedNodes.has(node.path);
  const totalChunks = countChunks(node);

  return (
    <div style={{ marginLeft: depth > 0 ? 12 : 0 }}>
      <button
        onClick={() => toggleNode(node.path)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          width: "100%",
          padding: "3px 4px",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "inherit",
          fontSize: "11px",
          color: "#e0e0e0",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#0a0a0a")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
      >
        <span style={{ color: "#555", fontSize: "9px" }}>
          {isCollapsed ? "\u25B6" : "\u25BC"}
        </span>
        <span style={{ color: node.path === NO_PATH ? "#ff3333" : "#ffaa00", fontWeight: 700, letterSpacing: "0.5px" }}>
          {node.label}/
        </span>
        <span style={{ color: "#555", fontSize: "10px" }}>
          {totalChunks} chunks
        </span>
      </button>
      {!isCollapsed && (
        <div style={{ marginLeft: 12 }}>
          {node.children.map((child) => (
            <DirTreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              expandedChunks={expandedChunks}
              toggleChunk={toggleChunk}
              collapsedNodes={collapsedNodes}
              toggleNode={toggleNode}
              expandedSources={expandedSources}
              toggleSource={toggleSource}
            />
          ))}
          {node.sources.map((src) => (
            <SourceTreeNode
              key={src.source}
              source={src}
              dirPath={node.path}
              expandedChunks={expandedChunks}
              toggleChunk={toggleChunk}
              expandedSources={expandedSources}
              toggleNode={toggleSource}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceTreeNode({
  source,
  dirPath,
  expandedChunks,
  toggleChunk,
  expandedSources,
  toggleNode,
}: {
  source: SourceNode;
  dirPath: string;
  expandedChunks: Set<string>;
  toggleChunk: (key: string) => void;
  expandedSources: Set<string>;
  toggleNode: (key: string) => void;
}) {
  const nodeKey = `${dirPath}/${source.source}`;
  const isExpanded = expandedSources.has(nodeKey);

  return (
    <div>
      <button
        onClick={() => toggleNode(nodeKey)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          width: "100%",
          padding: "2px 4px",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "inherit",
          fontSize: "11px",
          color: "#b0b0b0",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#0a0a0a")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
      >
        <span style={{ color: "#555", fontSize: "9px" }}>
          {isExpanded ? "\u25BC" : "\u25B6"}
        </span>
        <span style={{ color: "#00cc33", fontWeight: 700, fontSize: "11px" }}>
          {source.source}
        </span>
        <span style={{ color: "#555", fontSize: "10px" }}>
          {source.chunks.length} chunks
        </span>
      </button>
      {isExpanded && (
        <div style={{ marginLeft: 12 }}>
          {source.chunks.map((chunk, ci) => {
            const key = `${nodeKey}:${ci}`;
            return (
              <ChunkRow
                key={key}
                chunk={chunk}
                index={key}
                expanded={expandedChunks.has(key)}
                onToggle={() => toggleChunk(key)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function countChunks(node: DirNode): number {
  let total = node.sources.reduce((sum, s) => sum + s.chunks.length, 0);
  for (const child of node.children) total += countChunks(child);
  return total;
}

export default function KnowledgePage() {
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [mode, setMode] = useState<"browse" | "search">("browse");

  useEffect(() => {
    fetchKnowledgeSources().then(setSources).catch(() => {});
  }, []);

  useEffect(() => {
    if (mode !== "browse") return;
    fetchKnowledgeChunks()
      .then(setChunks)
      .catch(() => {});
    setExpandedChunks(new Set());
  }, [mode]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!searchQuery.trim()) return;
      setSearching(true);
      setMode("search");
      searchKnowledge(searchQuery.trim())
        .then(setChunks)
        .catch(() => {})
        .finally(() => setSearching(false));
      setExpandedChunks(new Set());
    },
    [searchQuery],
  );

  const clearSearch = () => {
    setSearchQuery("");
    setMode("browse");
  };

  const toggleChunk = useCallback((key: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleNode = useCallback((key: string) => {
    setCollapsedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleSource = useCallback((key: string) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const tree = useMemo(() => buildTree(chunks), [chunks]);
  const totalChunks = sources.reduce((sum, s) => sum + s.chunk_count, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px", flexShrink: 0 }}>
        <span style={{ fontSize: "14px", fontWeight: 700, color: "#e0e0e0", letterSpacing: "1px" }}>
          KNOWLEDGE BASE
        </span>
        <span style={{ fontSize: "11px", color: "#555" }}>
          {sources.length} sources, {totalChunks} chunks
        </span>
        <form onSubmit={handleSearch} style={{ display: "flex", gap: "4px", marginLeft: "auto" }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="semantic search..."
            style={{
              fontSize: "11px",
              background: "#111",
              color: "#e0e0e0",
              border: "1px solid #222",
              borderRadius: "2px",
              padding: "2px 8px",
              width: "200px",
            }}
          />
          <button
            type="submit"
            disabled={searching}
            style={{
              fontSize: "11px",
              background: "#111",
              color: "#888",
              border: "1px solid #222",
              borderRadius: "2px",
              padding: "2px 8px",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            {searching ? "..." : "SEARCH"}
          </button>
          {mode === "search" && (
            <button
              type="button"
              onClick={clearSearch}
              style={{
                fontSize: "11px",
                background: "#111",
                color: "#555",
                border: "1px solid #222",
                borderRadius: "2px",
                padding: "2px 8px",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              CLEAR
            </button>
          )}
        </form>
      </div>

      {/* Tree view */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          background: "#111",
          border: "1px solid #1a1a1a",
          borderRadius: "3px",
          padding: "6px",
        }}
      >
        {mode === "search" && (
          <div style={{ fontSize: "11px", color: "#555", marginBottom: "4px" }}>
            {chunks.length} results for &quot;{searchQuery}&quot;
          </div>
        )}
        {tree.map((node) => (
          <DirTreeNode
            key={node.path}
            node={node}
            depth={0}
            expandedChunks={expandedChunks}
            toggleChunk={toggleChunk}
            collapsedNodes={collapsedNodes}
            toggleNode={toggleNode}
            expandedSources={expandedSources}
            toggleSource={toggleSource}
          />
        ))}
        {chunks.length === 0 && (
          <div style={{ color: "#333", textAlign: "center", padding: "8px", fontSize: "11px" }}>
            {mode === "search" ? "No results." : "No knowledge chunks."}
          </div>
        )}
      </div>
    </div>
  );
}
