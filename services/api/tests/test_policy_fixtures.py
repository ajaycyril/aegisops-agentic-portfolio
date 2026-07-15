import json
from pathlib import Path
from typing import Any, cast

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "configs" / "policies" / "fixtures"
ALLOWED_DECISION_POINTS = {
    "run_eligibility",
    "tool_access",
    "human_approval",
    "budget",
    "data_sensitivity",
}


def load_fixture(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_policy_fixtures_are_structured_json_inputs() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert fixture_paths
    for path in fixture_paths:
        payload = load_fixture(path)
        assert payload["decision_point"] in ALLOWED_DECISION_POINTS
        assert isinstance(payload["package"], str)
        assert payload["package"].startswith("aegisops.")
        assert isinstance(payload["input"], dict)
        assert isinstance(payload["expected"], dict)
        assert isinstance(payload["expected"]["allow"], bool)
        assert isinstance(payload["expected"]["requires_approval"], bool)


def test_incident_approval_policy_fixtures_cover_sensitive_actions() -> None:
    fixture_names = {
        path.name
        for path in FIXTURE_DIR.glob("approval_decision_incident_*.json")
    }

    assert fixture_names == {
        "approval_decision_incident_paging_reject_allowed.json",
        "approval_decision_incident_rollback_approve_allowed.json",
        "approval_decision_incident_update_self_approval_blocked.json",
    }
    requested_actions = {
        load_fixture(path)["input"]["requested_action"]
        for path in FIXTURE_DIR.glob("approval_decision_incident_*.json")
    }
    assert requested_actions == {"rollback", "paging_action", "incident_update"}


def test_support_approval_policy_fixtures_cover_customer_message() -> None:
    fixture_names = {
        path.name for path in FIXTURE_DIR.glob("approval_decision_support_*.json")
    }

    assert fixture_names == {
        "approval_decision_support_message_approve_allowed.json",
        "approval_decision_support_message_self_approval_blocked.json",
    }
    requested_actions = {
        load_fixture(path)["input"]["requested_action"]
        for path in FIXTURE_DIR.glob("approval_decision_support_*.json")
    }
    assert requested_actions == {"customer_message"}
