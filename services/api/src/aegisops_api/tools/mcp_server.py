from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from aegisops_api.tools.registry import ToolRegistry, get_tool_registry


def create_tool_contract_mcp_server(
    tool_registry: ToolRegistry | None = None,
    available_connectors: set[str] | None = None,
) -> FastMCP:
    registry = tool_registry or get_tool_registry()
    connectors = available_connectors or set()
    server = FastMCP(
        name="aegisops-tool-contracts",
        instructions=(
            "Expose AegisOps tool contracts for inspection. This server does not execute "
            "external actions; API authorization and OPA policy are required before runtime use."
        ),
    )

    @server.tool(
        name="list_tool_contracts",
        description="List typed AegisOps tool contracts and connector readiness.",
        structured_output=True,
    )
    def list_tool_contracts() -> list[dict[str, Any]]:
        return [
            tool.model_dump(mode="json")
            for tool in registry.list_tools(available_connectors=connectors)
        ]

    @server.tool(
        name="get_tool_contract",
        description="Get one typed AegisOps tool contract including JSON input/output schemas.",
        structured_output=True,
    )
    def get_tool_contract(tool_id: str) -> dict[str, Any]:
        return registry.get_tool(
            tool_id,
            available_connectors=connectors,
        ).model_dump(mode="json")

    return server
