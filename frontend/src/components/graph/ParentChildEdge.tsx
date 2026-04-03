"use client";

import { BaseEdge, getStraightPath, type EdgeProps } from "@xyflow/react";

export function ParentChildEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps) {
  const [edgePath] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
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
