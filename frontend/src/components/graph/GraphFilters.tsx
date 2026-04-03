"use client";

import { MESSAGE_TYPE_COLORS, type GraphFilters as Filters } from "./graphUtils";

const MESSAGE_TYPES = ["task", "result", "question", "answer", "guidance", "status_update"];
const TIME_RANGES = [
  { label: "1m", value: 1 },
  { label: "5m", value: 5 },
  { label: "15m", value: 15 },
  { label: "1h", value: 60 },
  { label: "6h", value: 360 },
  { label: "24h", value: 1440 },
  { label: "All", value: null },
];

interface GraphFiltersProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function GraphFilters({ filters, onChange }: GraphFiltersProps) {
  const toggleMessageType = (type: string) => {
    const next = new Set(filters.messageTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onChange({ ...filters, messageTypes: next });
  };

  return (
    <div
      style={{
        padding: "12px",
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <div style={{ color: "#888", marginBottom: 8, fontSize: 9, letterSpacing: 1 }}>
        FILTERS
      </div>

      {/* Show/hide toggles */}
      <label style={{ display: "flex", alignItems: "center", gap: 6, color: "#b0b0b0", marginBottom: 4, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={filters.showMessages}
          onChange={() => onChange({ ...filters, showMessages: !filters.showMessages })}
        />
        Show messages
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 6, color: "#b0b0b0", marginBottom: 8, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={filters.showSubtasks}
          onChange={() => onChange({ ...filters, showSubtasks: !filters.showSubtasks })}
        />
        Show subtasks
      </label>

      {/* Message type filters */}
      <div style={{ color: "#666", marginBottom: 4, fontSize: 9 }}>MESSAGE TYPES</div>
      {MESSAGE_TYPES.map((type) => (
        <label
          key={type}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            color: "#b0b0b0",
            marginBottom: 2,
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={filters.messageTypes.has(type)}
            onChange={() => toggleMessageType(type)}
          />
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: MESSAGE_TYPE_COLORS[type],
            }}
          />
          {type.replace("_", " ")}
        </label>
      ))}

      {/* Time range */}
      <div style={{ color: "#666", marginTop: 10, marginBottom: 4, fontSize: 9 }}>
        TIME RANGE
      </div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {TIME_RANGES.map(({ label, value }) => {
          const active = filters.timeRangeMinutes === value;
          return (
            <button
              key={label}
              onClick={() => onChange({ ...filters, timeRangeMinutes: value })}
              style={{
                background: active ? "#222" : "transparent",
                border: `1px solid ${active ? "#555" : "#222"}`,
                color: active ? "#e0e0e0" : "#666",
                borderRadius: 2,
                padding: "2px 6px",
                fontSize: 9,
                cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
