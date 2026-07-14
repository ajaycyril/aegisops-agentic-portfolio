from typing import Any

import httpx
from pydantic import BaseModel, Field


class PolicyEvaluationError(RuntimeError):
    pass


class PolicyDecision(BaseModel):
    package_path: str
    allowed: bool
    result: dict[str, Any]
    decision_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class OpaClient:
    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
        )

    async def evaluate(self, package_path: str, input_payload: dict[str, Any]) -> PolicyDecision:
        response = await self._client.post(
            f"/v1/data/{package_path.replace('.', '/')}/decision",
            json={"input": input_payload},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result")
        if not isinstance(result, dict):
            raise PolicyEvaluationError("OPA response must include an object result")

        allowed = result.get("allow", False)
        if not isinstance(allowed, bool):
            raise PolicyEvaluationError("OPA result.allow must be a boolean")

        requires_approval = result.get("requires_approval", False)
        if not isinstance(requires_approval, bool):
            raise PolicyEvaluationError("OPA result.requires_approval must be a boolean")

        reason_codes = result.get("reason_codes", [])
        if not isinstance(reason_codes, list) or not all(
            isinstance(reason_code, str) for reason_code in reason_codes
        ):
            raise PolicyEvaluationError("OPA result.reason_codes must be a list of strings")

        decision_id = payload.get("decision_id")
        if decision_id is not None and not isinstance(decision_id, str):
            raise PolicyEvaluationError("OPA decision_id must be a string when present")

        return PolicyDecision(
            package_path=package_path,
            allowed=allowed,
            result=result,
            decision_id=decision_id,
            reason_codes=reason_codes,
            requires_approval=requires_approval,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
