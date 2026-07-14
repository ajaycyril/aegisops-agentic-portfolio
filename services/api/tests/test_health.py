from fastapi.testclient import TestClient

from aegisops_api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "aegisops-api"}


def test_ready_endpoint_does_not_require_openai_key() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["live_runs_require_approval"] is True


def test_version_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"
