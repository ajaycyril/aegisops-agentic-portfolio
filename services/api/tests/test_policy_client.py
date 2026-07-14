import json
from typing import Any

import httpx
import pytest

from aegisops_api.policy import OpaClient, PolicyDecision, PolicyEvaluationError


@pytest.mark.asyncio
async def test_opa_client_posts_structured_input_to_decision_endpoint() -> None:
    captured_request: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_request["path"] = request.url.path
        captured_request["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "decision_id": "decision-123",
                "result": {
                    "allow": True,
                    "requires_approval": False,
                    "reason_codes": [],
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://opa.test") as http_client:
        client = OpaClient(base_url="http://opa.test", http_client=http_client)

        decision = await client.evaluate(
            "aegisops.tool_access",
            {"tool": {"risk_class": "read"}},
        )

    assert captured_request["path"] == "/v1/data/aegisops/tool_access/decision"
    assert captured_request["body"] == {"input": {"tool": {"risk_class": "read"}}}
    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.decision_id == "decision-123"


@pytest.mark.asyncio
async def test_opa_client_rejects_malformed_results() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": {"allow": "yes"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://opa.test") as http_client:
        client = OpaClient(base_url="http://opa.test", http_client=http_client)

        with pytest.raises(PolicyEvaluationError):
            await client.evaluate("aegisops.tool_access", {})


def test_policy_decision_result_retains_full_opa_payload() -> None:
    result = {
        "allow": False,
        "requires_approval": True,
        "reason_codes": ["approval_required"],
        "extra": {"risk": "write"},
    }

    decision = PolicyDecision(
        package_path="aegisops.tool_access",
        allowed=False,
        requires_approval=True,
        reason_codes=["approval_required"],
        result=result,
    )

    assert decision.result["extra"] == {"risk": "write"}
