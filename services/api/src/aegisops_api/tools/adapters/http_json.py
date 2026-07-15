from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import httpx

from aegisops_api.tools.adapters.base import ToolAdapterExecutionError


class HttpJsonSearchAdapter:
    def __init__(
        self,
        *,
        connector_name: str,
        connection_id: str,
        base_url: str,
        endpoint_path: str,
        response_key: str,
        id_alias: str | None = None,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._connector_name = connector_name
        self._connection_id = connection_id
        self._endpoint_path = endpoint_path
        self._response_key = response_key
        self._id_alias = id_alias
        self._api_key = api_key
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=20.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "aegisops-agentic-portfolio",
            },
        )

    async def execute(self, _tool_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            self._endpoint_path,
            headers=self._auth_headers(),
            json={
                "connection_id": self._connection_id,
                **input_payload,
            },
        )
        payload = self._parse_response(response)
        records = payload.get(self._response_key)
        if not isinstance(records, list):
            raise ToolAdapterExecutionError(
                reason_code="http_json_response_invalid",
                message=f"{self._connector_name} response must include {self._response_key} list.",
                http_status=502,
            )
        normalized_records: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                raise ToolAdapterExecutionError(
                    reason_code="http_json_response_invalid",
                    message=(
                        f"{self._connector_name} {self._response_key} items must be "
                        "JSON objects."
                    ),
                    http_status=502,
                )
            normalized_records.append(
                normalize_record(cast(dict[str, Any], record), id_alias=self._id_alias)
            )
        return {self._response_key: normalized_records}

    def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolAdapterExecutionError(
                reason_code="http_json_request_failed",
                message=(
                    f"{self._connector_name} request failed with status "
                    f"{response.status_code}."
                ),
                http_status=502,
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ToolAdapterExecutionError(
                reason_code="http_json_response_invalid",
                message=f"{self._connector_name} response was not valid JSON.",
                http_status=502,
            ) from exc
        if isinstance(payload, list):
            return {self._response_key: payload}
        if not isinstance(payload, dict):
            raise ToolAdapterExecutionError(
                reason_code="http_json_response_invalid",
                message=f"{self._connector_name} response was not a JSON object or list.",
                http_status=502,
            )
        return cast(dict[str, Any], payload)


class ObservabilityLogSearchAdapter(HttpJsonSearchAdapter):
    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        http_client: httpx.AsyncClient | None = None,
    ) -> ObservabilityLogSearchAdapter:
        return cls(
            connector_name="Observability",
            connection_id=environment["OBSERVABILITY_CONNECTION_ID"],
            base_url=environment["OBSERVABILITY_API_BASE_URL"],
            endpoint_path=environment.get("OBSERVABILITY_LOG_SEARCH_PATH", "/logs/search"),
            response_key="events",
            id_alias="event_id",
            api_key=environment.get("OBSERVABILITY_API_KEY"),
            http_client=http_client,
        )


class DeploymentEventSearchAdapter(HttpJsonSearchAdapter):
    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        http_client: httpx.AsyncClient | None = None,
    ) -> DeploymentEventSearchAdapter:
        return cls(
            connector_name="Deployment Events",
            connection_id=environment["DEPLOYMENTS_CONNECTION_ID"],
            base_url=environment["DEPLOYMENTS_API_BASE_URL"],
            endpoint_path=environment.get("DEPLOYMENTS_SEARCH_PATH", "/deployments/search"),
            response_key="deployments",
            id_alias="deployment_id",
            api_key=environment.get("DEPLOYMENTS_API_KEY"),
            http_client=http_client,
        )


def normalize_record(record: dict[str, Any], *, id_alias: str | None = None) -> dict[str, Any]:
    normalized = dict(record)
    if "source_uri" not in normalized and isinstance(normalized.get("url"), str):
        normalized["source_uri"] = normalized["url"]
    if (
        id_alias is not None
        and id_alias not in normalized
        and isinstance(normalized.get("id"), str)
    ):
        normalized[id_alias] = normalized["id"]
    return normalized
