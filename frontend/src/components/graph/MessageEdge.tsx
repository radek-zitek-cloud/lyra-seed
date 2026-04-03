"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import { MESSAGE_TYPE_COLORS } from "./graphUtils";

export function MessageEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  data,
}: EdgeProps) {
  // Use high curvature so message edges arc away from straight parent-child lines
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: 0.4,
  });

  const messageType = (data?.messageType as string) ?? "task";
  const color = MESSAGE_TYPE_COLORS[messageType] ?? "#888";

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: 1.5,
          strokeDasharray: "5 3",
          opacity: 0.7,
        }}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              fontSize: 8,
              fontFamily: "'JetBrains Mono', monospace",
              color,
              background: "#0a0a0a",
              padding: "1px 4px",
              borderRadius: 2,
              border: `1px solid ${color}33`,
              pointerEvents: "none",
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
