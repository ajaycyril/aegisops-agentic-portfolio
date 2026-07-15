import json
from pathlib import Path

import httpx
import pytest

from aegisops_api.tools.adapters.base import ToolAdapterExecutionError
from aegisops_api.tools.adapters.http_json import (
    DeploymentEventSearchAdapter,
    ObservabilityLogSearchAdapter,
)
from aegisops_api.tools.adapters.registry import create_default_tool_adapter_registry


@pytest.mark.asyncio
async def test_observability_adapter_posts_query_to_configured_endpoint() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/v1/logs/search"
        assert request.headers["authorization"] == "Bearer obs-token"
        assert json.loads(request.content) == {
            "connection_id": "otel-prod",
            "service": "checkout-api",
            "time_window": {
                "start": "2026-07-15T10:00:00Z",
                "end": "2026-07-15T10:15:00Z",
            },
            "severity": "error",
        }
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "id": "evt_01JZ9",
                        "message": "payment provider timeout",
                        "url": "https://logs.example/events/evt_01JZ9",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://observability.example",
    ) as client:
        adapter = ObservabilityLogSearchAdapter.from_environment(
            {
                "OBSERVABILITY_CONNECTION_ID": "otel-prod",
                "OBSERVABILITY_API_BASE_URL": "https://observability.example",
                "OBSERVABILITY_LOG_SEARCH_PATH": "/v1/logs/search",
                "OBSERVABILITY_API_KEY": "obs-token",
            },
            http_client=client,
        )
        result = await adapter.execute(
            "observability_log_search",
            {
                "service": "checkout-api",
                "time_window": {
                    "start": "2026-07-15T10:00:00Z",
                    "end": "2026-07-15T10:15:00Z",
                },
                "severity": "error",
            },
        )

    assert result == {
        "events": [
            {
                "id": "evt_01JZ9",
                "message": "payment provider timeout",
                "url": "https://logs.example/events/evt_01JZ9",
                "source_uri": "https://logs.example/events/evt_01JZ9",
                "event_id": "evt_01JZ9",
            }
        ]
    }
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_deployment_adapter_accepts_bare_list_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/events/search"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {
            "connection_id": "deploy-prod",
            "service": "checkout-api",
            "time_window": {
                "start": "2026-07-15T09:30:00Z",
                "end": "2026-07-15T10:15:00Z",
            },
            "environment": "production",
        }
        return httpx.Response(
            200,
            json=[
                {
                    "id": "dep_20260715_1042",
                    "commit_sha": "8d63af90d8f3b7f1ed1ef37f1267f3f91fb3a111",
                    "url": "https://deployments.example/dep_20260715_1042",
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://deployments.example",
    ) as client:
        adapter = DeploymentEventSearchAdapter.from_environment(
            {
                "DEPLOYMENTS_CONNECTION_ID": "deploy-prod",
                "DEPLOYMENTS_API_BASE_URL": "https://deployments.example",
                "DEPLOYMENTS_SEARCH_PATH": "/events/search",
            },
            http_client=client,
        )
        result = await adapter.execute(
            "deployment_event_search",
            {
                "service": "checkout-api",
                "time_window": {
                    "start": "2026-07-15T09:30:00Z",
                    "end": "2026-07-15T10:15:00Z",
                },
                "environment": "production",
            },
        )

    assert result == {
        "deployments": [
            {
                "id": "dep_20260715_1042",
                "commit_sha": "8d63af90d8f3b7f1ed1ef37f1267f3f91fb3a111",
                "url": "https://deployments.example/dep_20260715_1042",
                "source_uri": "https://deployments.example/dep_20260715_1042",
                "deployment_id": "dep_20260715_1042",
            }
        ]
    }


@pytest.mark.asyncio
async def test_http_json_adapter_converts_upstream_http_error_to_tool_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://observability.example",
    ) as client:
        adapter = ObservabilityLogSearchAdapter.from_environment(
            {
                "OBSERVABILITY_CONNECTION_ID": "otel-prod",
                "OBSERVABILITY_API_BASE_URL": "https://observability.example",
            },
            http_client=client,
        )

        with pytest.raises(ToolAdapterExecutionError) as exc_info:
            await adapter.execute(
                "observability_log_search",
                {
                    "service": "checkout-api",
                    "time_window": {
                        "start": "2026-07-15T10:00:00Z",
                        "end": "2026-07-15T10:15:00Z",
                    },
                },
            )

    assert exc_info.value.reason_code == "http_json_request_failed"
    assert exc_info.value.http_status == 502


@pytest.mark.asyncio
async def test_http_json_adapter_rejects_invalid_record_shape() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"events": ["not-an-event"]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://observability.example",
    ) as client:
        adapter = ObservabilityLogSearchAdapter.from_environment(
            {
                "OBSERVABILITY_CONNECTION_ID": "otel-prod",
                "OBSERVABILITY_API_BASE_URL": "https://observability.example",
            },
            http_client=client,
        )

        with pytest.raises(ToolAdapterExecutionError) as exc_info:
            await adapter.execute(
                "observability_log_search",
                {
                    "service": "checkout-api",
                    "time_window": {
                        "start": "2026-07-15T10:00:00Z",
                        "end": "2026-07-15T10:15:00Z",
                    },
                },
            )

    assert exc_info.value.reason_code == "http_json_response_invalid"


def test_default_registry_uses_http_json_adapters_when_env_is_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OBSERVABILITY_CONNECTION_ID", "otel-prod")
    monkeypatch.setenv("OBSERVABILITY_API_BASE_URL", "https://observability.example")
    monkeypatch.setenv("DEPLOYMENTS_CONNECTION_ID", "deploy-prod")
    monkeypatch.setenv("DEPLOYMENTS_API_BASE_URL", "https://deployments.example")

    registry = create_default_tool_adapter_registry()

    assert isinstance(
        registry.get_adapter("observability_log_search"),
        ObservabilityLogSearchAdapter,
    )
    assert isinstance(
        registry.get_adapter("deployment_event_search"),
        DeploymentEventSearchAdapter,
    )
