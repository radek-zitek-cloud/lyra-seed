"use client";

type ConnectionState = "connecting" | "connected" | "disconnected";

const STATE_STYLES: Record<ConnectionState, { dot: string; label: string }> = {
  connected: { dot: "bg-green-500", label: "Connected" },
  connecting: { dot: "bg-yellow-500 animate-pulse", label: "Connecting..." },
  disconnected: { dot: "bg-red-500", label: "Disconnected" },
};

export function ConnectionStatus({ state }: { state: ConnectionState }) {
  const { dot, label } = STATE_STYLES[state];
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {label}
    </div>
  );
}
