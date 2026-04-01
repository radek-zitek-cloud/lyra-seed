"use client";

type ConnectionState = "connecting" | "connected" | "disconnected";

const STATE_STYLES: Record<ConnectionState, { color: string; label: string }> = {
  connected: { color: "#00ff41", label: "LIVE" },
  connecting: { color: "#ffaa00", label: "CONNECTING" },
  disconnected: { color: "#ff3333", label: "OFFLINE" },
};

export function ConnectionStatus({ state }: { state: ConnectionState }) {
  const { color, label } = STATE_STYLES[state];
  return (
    <span style={{ fontSize: "12px", color, fontWeight: 700 }}>
      {label}
    </span>
  );
}
