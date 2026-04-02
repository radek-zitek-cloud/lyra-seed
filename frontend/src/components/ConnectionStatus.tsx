"use client";

type ConnectionState = "connecting" | "connected" | "disconnected";

const STATE_STYLES: Record<ConnectionState, { color: string; label: string }> = {
  connected: { color: "#00ff41", label: "LIVE" },
  connecting: { color: "#ffaa00", label: "CONNECTING" },
  disconnected: { color: "#ff3333", label: "OFFLINE" },
};

export function ConnectionStatus({
  state,
  onConnect,
  onDisconnect,
}: {
  state: ConnectionState;
  onConnect?: () => void;
  onDisconnect?: () => void;
}) {
  const { color, label } = STATE_STYLES[state];
  const canToggle = onConnect && onDisconnect;

  if (!canToggle) {
    return (
      <span style={{ fontSize: "12px", color, fontWeight: 700 }}>
        {label}
      </span>
    );
  }

  const isConnected = state === "connected" || state === "connecting";

  return (
    <button
      onClick={isConnected ? onDisconnect : onConnect}
      style={{
        fontSize: "11px",
        fontWeight: 700,
        fontFamily: "inherit",
        letterSpacing: "1px",
        color,
        background: "none",
        border: `1px solid ${color}33`,
        borderRadius: "2px",
        padding: "2px 8px",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = `${color}33`;
      }}
    >
      {label}
    </button>
  );
}
