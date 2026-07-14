from __future__ import annotations

from typing import Any, Protocol


class ToolAdapterExecutionError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 502) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class ToolAdapterNotFoundError(ToolAdapterExecutionError):
    def __init__(self, tool_id: str) -> None:
        super().__init__(
            reason_code="tool_adapter_not_available",
            message=f"No execution adapter is registered for tool {tool_id}.",
            http_status=501,
        )


class ToolAdapter(Protocol):
    async def execute(self, tool_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        pass
