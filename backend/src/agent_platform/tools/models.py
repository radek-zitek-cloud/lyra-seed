"""Tool data models."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolType(StrEnum):
    """Type of tool."""

    MCP = "mcp"
    INTERNAL = "internal"


class Tool(BaseModel):
    """A tool available to agents."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    tool_type: ToolType
    source: str = ""


class ToolResult(BaseModel):
    """Result of a tool invocation."""

    success: bool
    output: str | dict[str, Any] = ""
    error: str | None = None
    duration_ms: int = 0
