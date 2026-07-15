from collections.abc import AsyncGenerator, Generator
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from aegisops_api import __version__
from aegisops_api.config import Settings, get_settings
from aegisops_api.connectors import ConnectorDetail, ConnectorNotFoundError, ConnectorSummary
from aegisops_api.connectors.registry import get_connector_registry
from aegisops_api.db.session import get_session
from aegisops_api.logging import configure_logging
from aegisops_api.policy import OpaClient, PolicyEvaluationError
from aegisops_api.tools import (
    OpaToolPolicyEvaluator,
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
    ToolDetail,
    ToolExecutionRejectedError,
    ToolNotFoundError,
    ToolPolicyEvaluator,
    ToolSummary,
    authorize_tool_call,
    execute_authorized_tool_call,
)
from aegisops_api.tools.adapters import (
    ToolAdapterExecutionError,
    ToolAdapterRegistry,
    create_default_tool_adapter_registry,
)
from aegisops_api.tools.registry import get_tool_registry
from aegisops_api.workflows import WorkflowDetail, WorkflowNotFoundError, WorkflowSummary
from aegisops_api.workflows.engineering_issue_to_pr import (
    ApprovalPolicyEvaluator,
    IssueToPrApprovalDecisionRequest,
    IssueToPrApprovalDecisionResponse,
    IssueToPrApprovalReviewRequest,
    IssueToPrApprovalReviewResponse,
    IssueToPrPrDraftAuthorizationRequest,
    IssueToPrPrDraftAuthorizationResponse,
    IssueToPrRunRejectedError,
    IssueToPrRunRequest,
    IssueToPrRunResponse,
    OpaApprovalPolicyEvaluator,
    OpenAIIssueToPrPlanner,
    OpenAIPlannerConfig,
    authorize_issue_to_pr_draft_pr,
    collect_engineering_issue_context,
    decide_issue_to_pr_approval,
    request_issue_to_pr_approval_review,
)
from aegisops_api.workflows.engineering_issue_to_pr.graph import IssueToPrPlanner
from aegisops_api.workflows.engineering_issue_to_pr.replay import ReplayFixtureError
from aegisops_api.workflows.incident_response_investigator import (
    IncidentInvestigationRejectedError,
    IncidentInvestigationRequest,
    IncidentInvestigationResponse,
    collect_incident_evidence,
)
from aegisops_api.workflows.incident_response_investigator import (
    ReplayFixtureError as IncidentReplayFixtureError,
)
from aegisops_api.workflows.registry import get_available_connectors, get_workflow_registry
from aegisops_api.workflows.runs import (
    OpaRunPolicyEvaluator,
    RunPolicyEvaluator,
    WorkflowRunStartRejectedError,
    WorkflowRunStartRequest,
    WorkflowRunStartResponse,
    start_workflow_run,
)

configure_logging()

app = FastAPI(
    title="AegisOps API",
    version=__version__,
    summary="API and agent runtime for the AegisOps agentic workflow portfolio.",
)


def get_database_session() -> Generator[Session, None, None]:
    try:
        yield from get_session()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="database is not configured") from exc


SettingsDependency = Annotated[Settings, Depends(get_settings)]


async def get_run_policy_evaluator(
    settings: SettingsDependency,
) -> AsyncGenerator[RunPolicyEvaluator, None]:
    if settings.opa_base_url is None:
        raise HTTPException(status_code=503, detail="OPA policy engine is not configured")

    opa_client = OpaClient(str(settings.opa_base_url))
    try:
        yield OpaRunPolicyEvaluator(opa_client)
    finally:
        await opa_client.aclose()


async def get_tool_policy_evaluator(
    settings: SettingsDependency,
) -> AsyncGenerator[ToolPolicyEvaluator, None]:
    if settings.opa_base_url is None:
        raise HTTPException(status_code=503, detail="OPA policy engine is not configured")

    opa_client = OpaClient(str(settings.opa_base_url))
    try:
        yield OpaToolPolicyEvaluator(opa_client)
    finally:
        await opa_client.aclose()


async def get_approval_policy_evaluator(
    settings: SettingsDependency,
) -> AsyncGenerator[ApprovalPolicyEvaluator, None]:
    if settings.opa_base_url is None:
        raise HTTPException(status_code=503, detail="OPA policy engine is not configured")

    opa_client = OpaClient(str(settings.opa_base_url))
    try:
        yield OpaApprovalPolicyEvaluator(opa_client)
    finally:
        await opa_client.aclose()


def get_tool_adapter_registry() -> ToolAdapterRegistry:
    return create_default_tool_adapter_registry()


def build_engineering_issue_to_pr_planner(
    settings: Settings,
    session: Session,
    run_id: UUID,
    trace_id: str | None,
) -> IssueToPrPlanner | None:
    model = settings.openai_reasoning_model or settings.openai_default_model
    if settings.openai_api_key is None or model is None:
        return None
    return OpenAIIssueToPrPlanner.from_api_key(
        api_key=settings.openai_api_key,
        session=session,
        run_id=run_id,
        config=OpenAIPlannerConfig(model=model),
        trace_id=trace_id,
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aegisops-api"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, object]:
    settings = get_settings()
    openai_planner_model = settings.openai_reasoning_model or settings.openai_default_model
    return {
        "status": "ready",
        "environment": settings.app_env,
        "policy_configured": settings.opa_base_url is not None,
        "database_configured": settings.database_url is not None,
        "live_runs_require_approval": settings.require_human_approval,
        "engineering_issue_to_pr_planner_configured": (
            settings.openai_api_key is not None and openai_planner_model is not None
        ),
        "openai_planner_model": openai_planner_model,
    }


@app.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {"version": __version__}


@app.get("/workflows", response_model=list[WorkflowSummary], tags=["workflows"])
async def list_workflows() -> list[WorkflowSummary]:
    registry = get_workflow_registry()
    return registry.list_workflows(available_connectors=get_available_connectors())


@app.get("/workflows/{workflow_id}", response_model=WorkflowDetail, tags=["workflows"])
async def get_workflow(workflow_id: str) -> WorkflowDetail:
    registry = get_workflow_registry()
    try:
        return registry.get_workflow(
            workflow_id,
            available_connectors=get_available_connectors(),
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc


@app.get("/connectors", response_model=list[ConnectorSummary], tags=["connectors"])
async def list_connectors() -> list[ConnectorSummary]:
    registry = get_connector_registry()
    return registry.list_connectors(configured_connectors=get_available_connectors())


@app.get("/connectors/{connector_id}", response_model=ConnectorDetail, tags=["connectors"])
async def get_connector(connector_id: str) -> ConnectorDetail:
    registry = get_connector_registry()
    try:
        return registry.get_connector(
            connector_id,
            configured_connectors=get_available_connectors(),
        )
    except ConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail="connector not found") from exc


@app.get("/tools", response_model=list[ToolSummary], tags=["tools"])
async def list_tools() -> list[ToolSummary]:
    registry = get_tool_registry()
    return registry.list_tools(available_connectors=get_available_connectors())


@app.get("/tools/{tool_id}", response_model=ToolDetail, tags=["tools"])
async def get_tool(tool_id: str) -> ToolDetail:
    registry = get_tool_registry()
    try:
        return registry.get_tool(
            tool_id,
            available_connectors=get_available_connectors(),
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail="tool not found") from exc


@app.post(
    "/tool-calls/authorize",
    response_model=ToolCallAuthorizationResponse,
    status_code=201,
    tags=["tools"],
)
async def authorize_tool_call_endpoint(
    request: ToolCallAuthorizationRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[ToolPolicyEvaluator, Depends(get_tool_policy_evaluator)],
) -> ToolCallAuthorizationResponse:
    try:
        return await authorize_tool_call(
            request=request,
            workflow_registry=get_workflow_registry(),
            tool_registry=get_tool_registry(),
            session=session,
            policy_evaluator=policy_evaluator,
            available_connectors=get_available_connectors(),
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail="tool not found") from exc
    except ToolExecutionRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="OPA policy evaluation failed") from exc


@app.post(
    "/tool-calls/{tool_call_id}/execute",
    response_model=ToolCallExecutionResponse,
    tags=["tools"],
)
async def execute_tool_call_endpoint(
    tool_call_id: UUID,
    request: ToolCallExecutionRequest,
    session: Annotated[Session, Depends(get_database_session)],
    adapter_registry: Annotated[ToolAdapterRegistry, Depends(get_tool_adapter_registry)],
) -> ToolCallExecutionResponse:
    try:
        return await execute_authorized_tool_call(
            tool_call_id=tool_call_id,
            request=request,
            tool_registry=get_tool_registry(),
            session=session,
            adapter_registry=adapter_registry,
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail="tool not found") from exc
    except ToolExecutionRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except ToolAdapterExecutionError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc


@app.post(
    "/workflow-runs",
    response_model=WorkflowRunStartResponse,
    status_code=201,
    tags=["workflow-runs"],
)
async def create_workflow_run(
    request: WorkflowRunStartRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[RunPolicyEvaluator, Depends(get_run_policy_evaluator)],
    settings: SettingsDependency,
) -> WorkflowRunStartResponse:
    registry = get_workflow_registry()
    try:
        return await start_workflow_run(
            request=request,
            registry=registry,
            session=session,
            policy_evaluator=policy_evaluator,
            available_connectors=get_available_connectors(),
            settings=settings,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    except WorkflowRunStartRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="OPA policy evaluation failed") from exc


@app.post(
    "/workflow-runs/{run_id}/engineering-issue-to-pr/evidence",
    response_model=IssueToPrRunResponse,
    tags=["workflow-runs"],
)
async def collect_engineering_issue_to_pr_evidence(
    run_id: UUID,
    request: IssueToPrRunRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[ToolPolicyEvaluator, Depends(get_tool_policy_evaluator)],
    adapter_registry: Annotated[ToolAdapterRegistry, Depends(get_tool_adapter_registry)],
    settings: SettingsDependency,
) -> IssueToPrRunResponse:
    try:
        planner = None
        if request.include_proposal:
            planner = build_engineering_issue_to_pr_planner(
                settings=settings,
                session=session,
                run_id=run_id,
                trace_id=request.trace_id,
            )
        return await collect_engineering_issue_context(
            run_id=run_id,
            request=request,
            session=session,
            workflow_registry=get_workflow_registry(),
            tool_registry=get_tool_registry(),
            policy_evaluator=policy_evaluator,
            adapter_registry=adapter_registry,
            available_connectors=get_available_connectors(),
            planner=planner,
        )
    except IssueToPrRunRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except ReplayFixtureError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (ToolExecutionRejectedError, ToolAdapterExecutionError) as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="workflow graph execution failed") from exc


@app.post(
    "/workflow-runs/{run_id}/engineering-issue-to-pr/approval-review",
    response_model=IssueToPrApprovalReviewResponse,
    status_code=201,
    tags=["workflow-runs"],
)
async def request_engineering_issue_to_pr_approval_review(
    run_id: UUID,
    request: IssueToPrApprovalReviewRequest,
    session: Annotated[Session, Depends(get_database_session)],
) -> IssueToPrApprovalReviewResponse:
    try:
        return await request_issue_to_pr_approval_review(
            run_id=run_id,
            request=request,
            session=session,
        )
    except IssueToPrRunRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc


@app.post(
    "/workflow-runs/{run_id}/engineering-issue-to-pr/approvals/{approval_id}/decision",
    response_model=IssueToPrApprovalDecisionResponse,
    tags=["workflow-runs"],
)
async def decide_engineering_issue_to_pr_approval(
    run_id: UUID,
    approval_id: UUID,
    request: IssueToPrApprovalDecisionRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[
        ApprovalPolicyEvaluator,
        Depends(get_approval_policy_evaluator),
    ],
) -> IssueToPrApprovalDecisionResponse:
    try:
        return await decide_issue_to_pr_approval(
            run_id=run_id,
            approval_id=approval_id,
            request=request,
            session=session,
            policy_evaluator=policy_evaluator,
        )
    except IssueToPrRunRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="OPA policy evaluation failed") from exc


@app.post(
    "/workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/authorize",
    response_model=IssueToPrPrDraftAuthorizationResponse,
    tags=["workflow-runs"],
)
async def authorize_engineering_issue_to_pr_draft_pr(
    run_id: UUID,
    request: IssueToPrPrDraftAuthorizationRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[ToolPolicyEvaluator, Depends(get_tool_policy_evaluator)],
) -> IssueToPrPrDraftAuthorizationResponse:
    try:
        return await authorize_issue_to_pr_draft_pr(
            run_id=run_id,
            request=request,
            session=session,
            workflow_registry=get_workflow_registry(),
            tool_registry=get_tool_registry(),
            policy_evaluator=policy_evaluator,
            available_connectors=get_available_connectors(),
        )
    except IssueToPrRunRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (WorkflowNotFoundError, ToolNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="workflow or tool not found") from exc
    except ToolExecutionRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="OPA policy evaluation failed") from exc


@app.post(
    "/workflow-runs/{run_id}/incident-response-investigator/evidence",
    response_model=IncidentInvestigationResponse,
    tags=["workflow-runs"],
)
async def collect_incident_response_evidence(
    run_id: UUID,
    request: IncidentInvestigationRequest,
    session: Annotated[Session, Depends(get_database_session)],
    policy_evaluator: Annotated[ToolPolicyEvaluator, Depends(get_tool_policy_evaluator)],
    adapter_registry: Annotated[ToolAdapterRegistry, Depends(get_tool_adapter_registry)],
) -> IncidentInvestigationResponse:
    try:
        return await collect_incident_evidence(
            run_id=run_id,
            request=request,
            session=session,
            workflow_registry=get_workflow_registry(),
            tool_registry=get_tool_registry(),
            policy_evaluator=policy_evaluator,
            adapter_registry=adapter_registry,
            available_connectors=get_available_connectors(),
        )
    except IncidentInvestigationRejectedError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except IncidentReplayFixtureError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (ToolExecutionRejectedError, ToolAdapterExecutionError) as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    except (PolicyEvaluationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="workflow graph execution failed") from exc
