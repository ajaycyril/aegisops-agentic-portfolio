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
    assert payload["engineering_issue_to_pr_planner_configured"] is False
    assert payload["openai_planner_model"] is None


def test_version_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


def test_workflows_endpoint_lists_disabled_real_workflows() -> None:
    client = TestClient(app)

    response = client.get("/workflows")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 10
    assert {workflow["id"] for workflow in payload} >= {
        "engineering_issue_to_pr",
        "incident_response_investigator",
    }
    assert all(workflow["enabled"] is False for workflow in payload)


def test_workflow_detail_endpoint_returns_config_contract() -> None:
    client = TestClient(app)

    response = client.get("/workflows/engineering_issue_to_pr")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "engineering_issue_to_pr"
    assert payload["data_policy"]["fake_data_allowed"] is False
    assert payload["data_policy"]["regex_business_extraction_allowed"] is False
    assert payload["missing_connectors"] == ["github"]


def test_workflow_detail_endpoint_returns_404_for_unknown_workflow() -> None:
    client = TestClient(app)

    response = client.get("/workflows/not_a_workflow")

    assert response.status_code == 404
