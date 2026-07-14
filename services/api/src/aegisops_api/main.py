from fastapi import FastAPI

from aegisops_api import __version__
from aegisops_api.config import get_settings
from aegisops_api.logging import configure_logging

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
