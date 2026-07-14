from collections.abc import AsyncGenerator, Generator
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from aegisops_api import __version__
from aegisops_api.config import Settings, get_settings
from aegisops_api.db.session import get_session
from aegisops_api.logging import configure_logging
from aegisops_api.policy import OpaClient, PolicyEvaluationError
from aegisops_api.tools import ToolDetail, ToolNotFoundError, ToolSummary
from aegisops_api.tools.registry import get_tool_registry
from aegisops_api.workflows import WorkflowDetail, WorkflowNotFoundError, WorkflowSummary
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


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aegisops-api"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ready",
        "environment": settings.app_env,
        "policy_configured": settings.opa_base_url is not None,
        "database_configured": settings.database_url is not None,
        "live_runs_require_approval": settings.require_human_approval,
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
