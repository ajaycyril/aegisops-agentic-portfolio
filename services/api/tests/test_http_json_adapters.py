import json
from pathlib import Path

import httpx
import pytest

from aegisops_api.tools.adapters.base import ToolAdapterExecutionError
from aegisops_api.tools.adapters.http_json import (
    CrmCustomerProfileReadAdapter,
    DeploymentEventSearchAdapter,
    KnowledgeBaseSearchAdapter,
    ObservabilityLogSearchAdapter,
    SupportTicketReadAdapter,
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


@pytest.mark.asyncio
async def test_support_ticket_adapter_accepts_bare_object_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/tickets/get"
        assert request.headers["authorization"] == "Bearer support-token"
        assert json.loads(request.content) == {
            "connection_id": "support-prod",
            "ticket_id": "TCK-1024",
            "include_messages": True,
        }
        return httpx.Response(
            200,
            json={
                "id": "TCK-1024",
                "subject": "SSO lockout after domain migration",
                "customer_id": "cus_123",
                "url": "https://support.example/tickets/TCK-1024",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://support.example",
    ) as client:
        adapter = SupportTicketReadAdapter.from_environment(
            {
                "SUPPORT_SYSTEM_CONNECTION_ID": "support-prod",
                "SUPPORT_SYSTEM_API_BASE_URL": "https://support.example",
                "SUPPORT_TICKET_READ_PATH": "/tickets/get",
                "SUPPORT_SYSTEM_API_KEY": "support-token",
            },
            http_client=client,
        )
        result = await adapter.execute(
            "support_ticket_read",
            {"ticket_id": "TCK-1024", "include_messages": True},
        )

    assert result == {
        "ticket": {
            "id": "TCK-1024",
            "ticket_id": "TCK-1024",
            "subject": "SSO lockout after domain migration",
            "customer_id": "cus_123",
            "url": "https://support.example/tickets/TCK-1024",
            "source_uri": "https://support.example/tickets/TCK-1024",
        }
    }


@pytest.mark.asyncio
async def test_knowledge_base_adapter_normalizes_document_ids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/kb/search"
        assert json.loads(request.content) == {
            "connection_id": "kb-prod",
            "query": "SSO lockout",
            "limit": 5,
        }
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "id": "kb_42",
                        "title": "Troubleshoot enterprise SSO lockouts",
                        "excerpt": "Verify IdP domain migration and SCIM sync state.",
                        "url": "https://kb.example/articles/kb_42",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://kb.example",
    ) as client:
        adapter = KnowledgeBaseSearchAdapter.from_environment(
            {
                "KNOWLEDGE_BASE_CONNECTION_ID": "kb-prod",
                "KNOWLEDGE_BASE_API_BASE_URL": "https://kb.example",
                "KNOWLEDGE_BASE_SEARCH_PATH": "/kb/search",
            },
            http_client=client,
        )
        result = await adapter.execute(
            "knowledge_base_search",
            {"query": "SSO lockout", "limit": 5},
        )

    assert result == {
        "documents": [
            {
                "id": "kb_42",
                "document_id": "kb_42",
                "title": "Troubleshoot enterprise SSO lockouts",
                "excerpt": "Verify IdP domain migration and SCIM sync state.",
                "url": "https://kb.example/articles/kb_42",
                "source_uri": "https://kb.example/articles/kb_42",
            }
        ]
    }


def test_default_registry_uses_http_json_adapters_when_env_is_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OBSERVABILITY_CONNECTION_ID", "otel-prod")
    monkeypatch.setenv("OBSERVABILITY_API_BASE_URL", "https://observability.example")
    monkeypatch.setenv("DEPLOYMENTS_CONNECTION_ID", "deploy-prod")
    monkeypatch.setenv("DEPLOYMENTS_API_BASE_URL", "https://deployments.example")
    monkeypatch.setenv("SUPPORT_SYSTEM_CONNECTION_ID", "support-prod")
    monkeypatch.setenv("SUPPORT_SYSTEM_API_BASE_URL", "https://support.example")
    monkeypatch.setenv("CRM_CONNECTION_ID", "crm-prod")
    monkeypatch.setenv("CRM_API_BASE_URL", "https://crm.example")
    monkeypatch.setenv("KNOWLEDGE_BASE_CONNECTION_ID", "kb-prod")
    monkeypatch.setenv("KNOWLEDGE_BASE_API_BASE_URL", "https://kb.example")

    registry = create_default_tool_adapter_registry()

    assert isinstance(
        registry.get_adapter("observability_log_search"),
        ObservabilityLogSearchAdapter,
    )
    assert isinstance(
        registry.get_adapter("deployment_event_search"),
        DeploymentEventSearchAdapter,
    )
    assert isinstance(registry.get_adapter("support_ticket_read"), SupportTicketReadAdapter)
    assert isinstance(
        registry.get_adapter("crm_customer_profile_read"),
        CrmCustomerProfileReadAdapter,
    )
    assert isinstance(registry.get_adapter("knowledge_base_search"), KnowledgeBaseSearchAdapter)
