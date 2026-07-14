from __future__ import annotations

import base64
import time
from collections.abc import Mapping
from typing import Any, cast

import httpx
import jwt

from aegisops_api.tools.adapters.base import ToolAdapterExecutionError

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


class GitHubAppToolAdapter:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._client = http_client or httpx.AsyncClient(
            base_url=GITHUB_API_BASE_URL,
            timeout=20.0,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "aegisops-agentic-portfolio",
            },
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> GitHubAppToolAdapter:
        missing = [
            env_var
            for env_var in ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY")
            if not environment.get(env_var)
        ]
        if missing:
            raise ToolAdapterExecutionError(
                reason_code="connector_auth_missing",
                message=f"GitHub adapter is missing required env vars: {', '.join(missing)}.",
                http_status=503,
            )
        return cls(
            app_id=environment["GITHUB_APP_ID"],
            private_key=environment["GITHUB_APP_PRIVATE_KEY"],
        )

    async def execute(self, tool_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        if tool_id == "github_issue_read":
            return await self.read_issue(
                repository=str(input_payload["repository"]),
                issue_number=int(input_payload["issue_number"]),
            )
        if tool_id == "github_file_read":
            return await self.read_file(
                repository=str(input_payload["repository"]),
                path=str(input_payload["path"]),
                ref=str(input_payload["ref"]),
            )
        raise ToolAdapterExecutionError(
            reason_code="tool_adapter_not_available",
            message=f"GitHub adapter does not implement tool {tool_id}.",
            http_status=501,
        )

    async def read_issue(self, repository: str, issue_number: int) -> dict[str, Any]:
        owner, repo = split_repository(repository)
        token = await self._get_installation_token(owner, repo)
        response = await self._client.get(
            f"/repos/{owner}/{repo}/issues/{issue_number}",
            headers=self._installation_headers(token),
        )
        payload = self._parse_github_response(response)
        labels = payload.get("labels", [])
        author = payload.get("user") or {}
        return {
            "title": str(payload.get("title") or ""),
            "body": str(payload.get("body") or ""),
            "labels": [str(label.get("name")) for label in labels if isinstance(label, dict)],
            "author": str(author.get("login") or "") if isinstance(author, dict) else "",
            "url": str(payload.get("html_url") or ""),
        }

    async def read_file(self, repository: str, path: str, ref: str) -> dict[str, Any]:
        owner, repo = split_repository(repository)
        token = await self._get_installation_token(owner, repo)
        response = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            headers=self._installation_headers(token),
            params={"ref": ref},
        )
        payload = self._parse_github_response(response)
        if payload.get("type") != "file":
            raise ToolAdapterExecutionError(
                reason_code="github_content_not_file",
                message="GitHub content response is not a file.",
                http_status=422,
            )
        content = decode_github_content(payload)
        return {
            "path": str(payload.get("path") or path),
            "ref": ref,
            "content": content,
            "sha": str(payload.get("sha") or ""),
        }

    async def _get_installation_token(self, owner: str, repo: str) -> str:
        app_jwt = create_github_app_jwt(self._app_id, self._private_key)
        installation_response = await self._client.get(
            f"/repos/{owner}/{repo}/installation",
            headers=self._app_headers(app_jwt),
        )
        installation_payload = self._parse_github_response(installation_response)
        installation_id = installation_payload.get("id")
        if not isinstance(installation_id, int):
            raise ToolAdapterExecutionError(
                reason_code="github_installation_missing",
                message="GitHub installation response did not include an installation id.",
                http_status=502,
            )

        token_response = await self._client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers=self._app_headers(app_jwt),
        )
        token_payload = self._parse_github_response(token_response)
        token = token_payload.get("token")
        if not isinstance(token, str) or not token:
            raise ToolAdapterExecutionError(
                reason_code="github_installation_token_missing",
                message="GitHub token response did not include an installation token.",
                http_status=502,
            )
        return token

    def _app_headers(self, app_jwt: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {app_jwt}"}

    def _installation_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _parse_github_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolAdapterExecutionError(
                reason_code="github_request_failed",
                message=f"GitHub API request failed with status {response.status_code}.",
                http_status=502,
            ) from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise ToolAdapterExecutionError(
                reason_code="github_response_invalid",
                message="GitHub API response was not a JSON object.",
                http_status=502,
            )
        return cast(dict[str, Any], payload)


def create_github_app_jwt(app_id: str, private_key: str) -> str:
    issued_at = int(time.time()) - 60
    expires_at = issued_at + 540
    encoded = jwt.encode(
        {"iat": issued_at, "exp": expires_at, "iss": app_id},
        private_key,
        algorithm="RS256",
    )
    return str(encoded)


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1] or "/" in parts[1]:
        raise ToolAdapterExecutionError(
            reason_code="github_repository_invalid",
            message="GitHub repository must use owner/name form.",
            http_status=422,
        )
    return parts[0], parts[1]


def decode_github_content(payload: dict[str, Any]) -> str:
    encoding = payload.get("encoding")
    raw_content = payload.get("content")
    if encoding != "base64" or not isinstance(raw_content, str):
        raise ToolAdapterExecutionError(
            reason_code="github_content_encoding_unsupported",
            message="GitHub file content was not base64 encoded.",
            http_status=502,
        )
    compact_content = "".join(raw_content.splitlines())
    return base64.b64decode(compact_content).decode("utf-8")
