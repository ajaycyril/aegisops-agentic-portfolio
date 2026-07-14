from fastapi import FastAPI, HTTPException

from aegisops_api import __version__
from aegisops_api.config import get_settings
from aegisops_api.logging import configure_logging
from aegisops_api.workflows import WorkflowDetail, WorkflowNotFoundError, WorkflowSummary
from aegisops_api.workflows.registry import get_available_connectors, get_workflow_registry

configure_logging()

app = FastAPI(
    title="AegisOps API",
    version=__version__,
    summary="API and agent runtime for the AegisOps agentic workflow portfolio.",
)


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
