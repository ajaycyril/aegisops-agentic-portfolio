from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRIC_DIR = REPO_ROOT / "configs" / "evals" / "rubrics"
WORKFLOW_DIR = REPO_ROOT / "configs" / "workflows"
ALLOWED_ARTIFACT_TYPES = {"patch_proposal", "rca_draft", "response_draft"}
ALLOWED_ENFORCEMENT = {"deterministic", "human_review", "llm_judge", "schema"}


def load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def workflow_ids() -> set[str]:
    return {load_yaml(path)["id"] for path in WORKFLOW_DIR.glob("*.yaml")}


def test_eval_rubrics_are_weighted_source_grounded_contracts() -> None:
    rubric_paths = sorted(RUBRIC_DIR.glob("*.yaml"))

    assert {path.name for path in rubric_paths} == {
        "customer_support_response_draft.yaml",
        "engineering_issue_to_pr_proposal.yaml",
        "incident_response_rca.yaml",
    }
    valid_workflow_ids = workflow_ids()
    for path in rubric_paths:
        rubric = load_yaml(path)
        assert rubric["version"] == 1
        assert rubric["workflow_id"] in valid_workflow_ids
        assert rubric["artifact_type"] in ALLOWED_ARTIFACT_TYPES
        assert 0 < rubric["minimum_score"] <= 1
        assert rubric["data_policy"] == {
            "fake_data_allowed": False,
            "replay_allowed_from_real_runs": True,
            "regex_business_extraction_allowed": False,
        }
        assert rubric["evidence_requirements"]["require_source_evidence_uris"] is True
        assert rubric["evidence_requirements"]["allow_uncited_claims"] is False
        dimensions = rubric["dimensions"]
        assert dimensions
        assert abs(sum(dimension["weight"] for dimension in dimensions) - 1.0) < 0.0001
        assert any(dimension["required"] for dimension in dimensions)
        for dimension in dimensions:
            assert dimension["enforcement"] in ALLOWED_ENFORCEMENT
            assert dimension["checks"]
            assert all(isinstance(check, str) and check for check in dimension["checks"])


def test_eval_rubrics_keep_sensitive_actions_approval_gated() -> None:
    support = load_yaml(RUBRIC_DIR / "customer_support_response_draft.yaml")
    incident = load_yaml(RUBRIC_DIR / "incident_response_rca.yaml")
    engineering = load_yaml(RUBRIC_DIR / "engineering_issue_to_pr_proposal.yaml")

    assert support["approval_requirements"] == {
        "customer_message": "approval_required",
        "refund": "approval_required",
        "account_change": "approval_required",
    }
    assert incident["approval_requirements"] == {
        "rollback": "approval_required",
        "incident_update": "approval_required",
        "paging_action": "approval_required",
    }
    assert engineering["approval_requirements"] == {
        "branch_creation": "approval_required",
        "pull_request_creation": "approval_required",
        "external_comment": "approval_required",
    }
