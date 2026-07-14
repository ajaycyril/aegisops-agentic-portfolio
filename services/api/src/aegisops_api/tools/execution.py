from __future__ import annotations

import json
from hashlib import sha256
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator, ValidationError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import Approval, ToolCall, utc_now
from aegisops_api.policy import OpaClient, PolicyDecision
from aegisops_api.tools.adapters import ToolAdapterExecutionError, ToolAdapterRegistry
from aegisops_api.tools.registry import ToolDetail, ToolRegistry
from aegisops_api.workflows.registry import AutonomyLevel, WorkflowDetail, WorkflowRegistry

ToolCallAuthorizationStatus = Literal["pending", "blocked"]
ToolExecutionState = Literal["authorized_not_executed", "blocked_before_execution"]
ToolCallExecutionStatus = Literal["succeeded"]
ToolExecutedState = Literal["executed"]


class ToolExecutionRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class ToolCallAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    workflow_id: str
    tool_id: str
    autonomy_level: AutonomyLevel
    input_payload: dict[str, Any] = Field(default_factory=dict)
    approval_id: UUID | None = None
    actor_id: str | None = None
    trace_id: str | None = None


class ToolPolicyDecisionSummary(BaseModel):
    allowed: bool
    requires_approval: bool
    decision_id: str | None
    reason_codes: list[str]


class ToolCallAuthorizationResponse(BaseModel):
    id: UUID
    run_id: UUID
    workflow_id: str
    tool_id: str
    status: ToolCallAuthorizationStatus
    execution_state: ToolExecutionState
    risk_class: str
    policy_decision: ToolPolicyDecisionSummary


class ToolCallExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_payload: dict[str, Any] = Field(default_factory=dict)
    actor_id: str | None = None
    trace_id: str | None = None


class ToolCallExecutionResponse(BaseModel):
    id: UUID
    run_id: UUID
    workflow_id: str
    tool_id: str
    status: ToolCallExecutionStatus
    execution_state: ToolExecutedState
    output_hash: str
    output_payload: dict[str, Any]
    latency_ms: int


class ToolPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        pass


class OpaToolPolicyEvaluator:
    def __init__(self, opa_client: OpaClient) -> None:
        self._opa_client = opa_client

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        return await self._opa_client.evaluate("aegisops.tool_access", input_payload)


async def authorize_tool_call(
    request: ToolCallAuthorizationRequest,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    session: Session,
    policy_evaluator: ToolPolicyEvaluator,
    available_connectors: set[str],
) -> ToolCallAuthorizationResponse:
    workflow = workflow_registry.get_workflow(
        request.workflow_id,
        available_connectors=available_connectors,
    )
    tool = tool_registry.get_tool(request.tool_id, available_connectors=available_connectors)
    ensure_tool_call_can_be_considered(request, workflow, tool)
    validate_tool_input(request.input_payload, tool)
    approval_status = get_approval_status(session, request)
    policy_input = build_tool_policy_input(
        request=request,
        workflow=workflow,
        tool=tool,
        approval_status=approval_status,
    )
    decision = await policy_evaluator.evaluate(policy_input)

    status: ToolCallAuthorizationStatus = "pending" if decision.allowed else "blocked"
    execution_state: ToolExecutionState = (
        "authorized_not_executed" if decision.allowed else "blocked_before_execution"
    )

    try:
        tool_call = ToolCall(
            id=uuid4(),
            run_id=request.run_id,
            approval_id=request.approval_id if approval_status == "approved" else None,
            tool_name=tool.id,
            tool_version=f"schema-{hash_payload(tool.input_schema)[:12]}",
            risk_class=tool.risk_class,
            input_schema_hash=hash_payload(tool.input_schema),
            input_hash=hash_payload(request.input_payload),
            status=status,
            policy_decision_id=decision.decision_id,
            trace_id=request.trace_id,
            call_metadata={
                "workflow_id": request.workflow_id,
                "tool_id": tool.id,
                "connector": tool.connector,
                "mcp_server": tool.mcp_server,
                "required_scopes": tool.required_scopes,
                "policy_result": decision.result,
                "execution_state": execution_state,
            },
        )
        session.add(tool_call)
        session.flush()
        write_audit_event(
            session,
            AuditEventInput(
                run_id=request.run_id,
                workflow_id=request.workflow_id,
                event_type=f"tool_call.{status}",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="tool_call.authorize",
                resource_type="tool_call",
                resource_id=str(tool_call.id),
                policy_decision_id=decision.decision_id,
                trace_id=request.trace_id,
                payload={
                    "tool_id": tool.id,
                    "risk_class": tool.risk_class,
                    "status": status,
                    "execution_state": execution_state,
                    "policy_reason_codes": decision.reason_codes,
                },
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return ToolCallAuthorizationResponse(
        id=tool_call.id,
        run_id=request.run_id,
        workflow_id=request.workflow_id,
        tool_id=tool.id,
        status=status,
        execution_state=execution_state,
        risk_class=tool.risk_class,
        policy_decision=ToolPolicyDecisionSummary(
            allowed=decision.allowed,
            requires_approval=decision.requires_approval,
            decision_id=decision.decision_id,
            reason_codes=decision.reason_codes,
        ),
    )


async def execute_authorized_tool_call(
    tool_call_id: UUID,
    request: ToolCallExecutionRequest,
    tool_registry: ToolRegistry,
    session: Session,
    adapter_registry: ToolAdapterRegistry,
) -> ToolCallExecutionResponse:
    tool_call = session.get(ToolCall, tool_call_id)
    if tool_call is None:
        raise ToolExecutionRejectedError(
            reason_code="tool_call_not_found",
            message="Tool call record was not found.",
            http_status=404,
        )

    metadata = tool_call.call_metadata or {}
    workflow_id = require_metadata_string(metadata, "workflow_id")
    tool_id = require_metadata_string(metadata, "tool_id")
    connector = require_metadata_string(metadata, "connector")
    is_authorized_pending = (
        tool_call.status == "pending"
        and metadata.get("execution_state") == "authorized_not_executed"
    )
    if not is_authorized_pending:
        raise ToolExecutionRejectedError(
            reason_code="tool_call_not_executable",
            message="Tool call is not in an authorized pending state.",
        )
    if hash_payload(request.input_payload) != tool_call.input_hash:
        raise ToolExecutionRejectedError(
            reason_code="tool_input_hash_mismatch",
            message="Execution input does not match the authorized tool call input.",
        )

    tool = tool_registry.get_tool(tool_id, available_connectors={connector})
    validate_tool_input(request.input_payload, tool)

    started_at = perf_counter()
    try:
        adapter = adapter_registry.get_adapter(tool.id)
        tool_call.status = "running"
        session.flush()
        output_payload = await adapter.execute(tool.id, request.input_payload)
        validate_tool_output(output_payload, tool)
    except ToolAdapterExecutionError as exc:
        tool_call.status = "failed"
        tool_call.completed_at = utc_now()
        tool_call.error_message = exc.message
        tool_call.call_metadata = {
            **metadata,
            "execution_state": "failed",
            "adapter_reason_code": exc.reason_code,
        }
        write_audit_event(
            session,
            AuditEventInput(
                run_id=tool_call.run_id,
                workflow_id=workflow_id,
                event_type="tool_call.failed",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="tool_call.execute",
                resource_type="tool_call",
                resource_id=str(tool_call.id),
                policy_decision_id=tool_call.policy_decision_id,
                trace_id=request.trace_id or tool_call.trace_id,
                payload={
                    "tool_id": tool.id,
                    "risk_class": tool.risk_class,
                    "reason_code": exc.reason_code,
                },
            ),
        )
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise

    latency_ms = int((perf_counter() - started_at) * 1000)
    output_hash = hash_payload(output_payload)
    tool_call.status = "succeeded"
    tool_call.output_hash = output_hash
    tool_call.completed_at = utc_now()
    tool_call.latency_ms = latency_ms
    tool_call.call_metadata = {
        **metadata,
        "execution_state": "executed",
        "adapter": f"{connector}_adapter",
        "output_schema_hash": hash_payload(tool.output_schema),
    }
    write_audit_event(
        session,
        AuditEventInput(
            run_id=tool_call.run_id,
            workflow_id=workflow_id,
            event_type="tool_call.succeeded",
            actor_type="user" if request.actor_id else "system",
            actor_id=request.actor_id,
            action="tool_call.execute",
            resource_type="tool_call",
            resource_id=str(tool_call.id),
            policy_decision_id=tool_call.policy_decision_id,
            trace_id=request.trace_id or tool_call.trace_id,
            payload={
                "tool_id": tool.id,
                "risk_class": tool.risk_class,
                "latency_ms": latency_ms,
                "output_hash": output_hash,
            },
        ),
    )
    session.commit()

    return ToolCallExecutionResponse(
        id=tool_call.id,
        run_id=tool_call.run_id,
        workflow_id=workflow_id,
        tool_id=tool.id,
        status="succeeded",
        execution_state="executed",
        output_hash=output_hash,
        output_payload=output_payload,
        latency_ms=latency_ms,
    )


def ensure_tool_call_can_be_considered(
    request: ToolCallAuthorizationRequest,
    workflow: WorkflowDetail,
    tool: ToolDetail,
) -> None:
    if workflow.status != "ready":
        raise ToolExecutionRejectedError(
            reason_code="workflow_not_ready",
            message=f"Workflow status is {workflow.status}.",
        )
    if request.workflow_id not in tool.allowed_workflows:
        raise ToolExecutionRejectedError(
            reason_code="tool_not_allowed_for_workflow",
            message="Tool contract does not allow this workflow.",
        )


def validate_tool_input(input_payload: dict[str, Any], tool: ToolDetail) -> None:
    try:
        Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator(tool.input_schema).validate(input_payload)
    except ValidationError as exc:
        raise ToolExecutionRejectedError(
            reason_code="tool_input_schema_invalid",
            message=f"Tool input failed schema validation: {exc.message}",
            http_status=422,
        ) from exc


def validate_tool_output(output_payload: dict[str, Any], tool: ToolDetail) -> None:
    try:
        Draft202012Validator.check_schema(tool.output_schema)
        Draft202012Validator(tool.output_schema).validate(output_payload)
    except ValidationError as exc:
        raise ToolAdapterExecutionError(
            reason_code="tool_output_schema_invalid",
            message=f"Tool output failed schema validation: {exc.message}",
            http_status=502,
        ) from exc


def require_metadata_string(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ToolExecutionRejectedError(
            reason_code="tool_call_metadata_invalid",
            message=f"Tool call metadata is missing {key}.",
        )
    return value


def get_approval_status(session: Session, request: ToolCallAuthorizationRequest) -> str:
    if request.approval_id is None:
        return "not_requested"

    approval = session.get(Approval, request.approval_id)
    if approval is None:
        raise ToolExecutionRejectedError(
            reason_code="approval_not_found",
            message="Approval record was not found.",
            http_status=404,
        )
    if approval.run_id != request.run_id:
        raise ToolExecutionRejectedError(
            reason_code="approval_run_mismatch",
            message="Approval record does not belong to this run.",
        )
    if approval.status != "approved":
        raise ToolExecutionRejectedError(
            reason_code="approval_not_approved",
            message="Approval record is not approved.",
        )
    return "approved"


def build_tool_policy_input(
    request: ToolCallAuthorizationRequest,
    workflow: WorkflowDetail,
    tool: ToolDetail,
    approval_status: str,
) -> dict[str, Any]:
    return {
        "run_id": str(request.run_id),
        "workflow_id": workflow.id,
        "autonomy_level": request.autonomy_level,
        "connector_ready": tool.enabled,
        "tool": {
            "id": tool.id,
            "connector": tool.connector,
            "mcp_server": tool.mcp_server,
            "risk_class": tool.risk_class,
            "required_scopes": tool.required_scopes,
            "allowed_workflows": tool.allowed_workflows,
            "requires_approval": tool.requires_approval,
        },
        "approval": {
            "id": str(request.approval_id) if request.approval_id else None,
            "status": approval_status,
        },
    }


def hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()
