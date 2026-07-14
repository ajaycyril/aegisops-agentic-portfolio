import base64

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from aegisops_api.tools.adapters.github import GitHubAppToolAdapter


def create_test_private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.mark.asyncio
async def test_github_app_adapter_reads_issue_through_installation_token() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET" and request.url.path == "/repos/owner/repo/installation":
            assert request.headers["authorization"].startswith("Bearer ")
            return httpx.Response(200, json={"id": 101})
        if request.method == "POST" and request.url.path == "/app/installations/101/access_tokens":
            assert request.headers["authorization"].startswith("Bearer ")
            return httpx.Response(200, json={"token": "installation-token"})
        if request.method == "GET" and request.url.path == "/repos/owner/repo/issues/12":
            assert request.headers["authorization"] == "Bearer installation-token"
            return httpx.Response(
                200,
                json={
                    "title": "Real issue",
                    "body": "Issue body",
                    "labels": [{"name": "bug"}],
                    "user": {"login": "octocat"},
                    "html_url": "https://github.com/owner/repo/issues/12",
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.com") as client:
        adapter = GitHubAppToolAdapter(
            app_id="123",
            private_key=create_test_private_key(),
            http_client=client,
        )
        result = await adapter.execute(
            "github_issue_read",
            {"repository": "owner/repo", "issue_number": 12},
        )

    assert result == {
        "title": "Real issue",
        "body": "Issue body",
        "labels": ["bug"],
        "author": "octocat",
        "url": "https://github.com/owner/repo/issues/12",
    }
    assert [request.url.path for request in requests] == [
        "/repos/owner/repo/installation",
        "/app/installations/101/access_tokens",
        "/repos/owner/repo/issues/12",
    ]


@pytest.mark.asyncio
async def test_github_app_adapter_reads_file_content() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/repos/owner/repo/installation":
            return httpx.Response(200, json={"id": 101})
        if request.method == "POST" and request.url.path == "/app/installations/101/access_tokens":
            return httpx.Response(200, json={"token": "installation-token"})
        if request.method == "GET" and request.url.path == "/repos/owner/repo/contents/src/app.py":
            assert request.url.params["ref"] == "main"
            encoded = base64.b64encode(b"print('hello')\n").decode("utf-8")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": "src/app.py",
                    "encoding": "base64",
                    "content": encoded,
                    "sha": "abc123",
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.com") as client:
        adapter = GitHubAppToolAdapter(
            app_id="123",
            private_key=create_test_private_key(),
            http_client=client,
        )
        result = await adapter.execute(
            "github_file_read",
            {"repository": "owner/repo", "path": "src/app.py", "ref": "main"},
        )

    assert result == {
        "path": "src/app.py",
        "ref": "main",
        "content": "print('hello')\n",
        "sha": "abc123",
    }
