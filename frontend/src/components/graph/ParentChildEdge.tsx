"use client";

import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

export function ParentChildEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const isChildRunning = data?.childStatus === "running";

  return (
    <BaseEdge
      path={edgePath}
      style={{
        stroke: "#333",
        strokeWidth: 2,
        strokeDasharray: isChildRunning ? "6 3" : "none",
      }}
    />
  );
}
