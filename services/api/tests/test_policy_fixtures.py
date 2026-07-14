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
