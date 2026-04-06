"""Date/time tool — lets agents check the current date and time."""

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_platform.tools.models import Tool, ToolResult, ToolType


class DateTimeToolProvider:
    """ToolProvider exposing a get_current_time tool."""

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_current_time",
                description=(
                    "Get the current date and time. "
                    "Optionally specify a timezone (e.g. 'Europe/Prague', 'US/Eastern')."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": (
                                "IANA timezone name (e.g. 'Europe/Prague', "
                                "'America/New_York'). Defaults to UTC."
                            ),
                        },
                    },
                    "required": [],
                },
                tool_type=ToolType.INTERNAL,
                source="datetime",
            ),
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        start = time.monotonic()
        if name != "get_current_time":
            return ToolResult(
                success=False, error=f"Unknown tool: {name}"
            )

        tz_name = arguments.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error=f"Unknown timezone: {tz_name}",
                duration_ms=duration,
            )

        now = datetime.now(tz)
        duration = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=True,
            output=(
                f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                f"({now.strftime('%A')})"
            ),
            duration_ms=duration,
        )
