from pathlib import Path

import pytest

from aegisops_api.workflows.registry import (
    DEFAULT_WORKFLOW_CONFIG_DIR,
    WorkflowRegistry,
    WorkflowRegistryError,
    load_workflow_config,
)


def test_loads_all_workflow_configs() -> None:
    registry = WorkflowRegistry.from_directory(DEFAULT_WORKFLOW_CONFIG_DIR)

    workflows = registry.list_workflows()

    assert len(workflows) == 10
    assert {workflow.id for workflow in workflows} >= {
        "engineering_issue_to_pr",
        "customer_support_escalation",
        "incident_response_investigator",
    }


def test_workflows_are_disabled_without_real_connectors() -> None:
    registry = WorkflowRegistry.from_directory(DEFAULT_WORKFLOW_CONFIG_DIR)

    workflows = registry.list_workflows(available_connectors=set())

    assert workflows
    assert all(workflow.enabled is False for workflow in workflows)
    assert all(workflow.disabled_reason is not None for workflow in workflows)


def test_workflow_detail_reports_missing_connectors() -> None:
    registry = WorkflowRegistry.from_directory(DEFAULT_WORKFLOW_CONFIG_DIR)

    workflow = registry.get_workflow("engineering_issue_to_pr", available_connectors=set())

    assert workflow.id == "engineering_issue_to_pr"
    assert workflow.required_connectors == ["github"]
    assert workflow.missing_connectors == ["github"]
    assert workflow.data_policy.fake_data_allowed is False
    assert workflow.data_policy.regex_business_extraction_allowed is False


def test_workflow_config_rejects_fake_data_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(
        "\n".join(
            [
                "id: invalid",
                "name: Invalid",
                "domain: test",
                "status: planned",
                "enabled_when:",
                "  connectors: [github]",
                "patterns: [plan_execute]",
                "data_policy:",
                "  fake_data_allowed: true",
                "  replay_allowed_from_real_runs: true",
                "  regex_business_extraction_allowed: false",
                "default_autonomy: read_only",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fake data"):
        load_workflow_config(config_path)


def test_registry_rejects_empty_directories(tmp_path: Path) -> None:
    with pytest.raises(WorkflowRegistryError, match="no workflow configs"):
        WorkflowRegistry.from_directory(tmp_path)
