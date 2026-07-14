from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aegisops_api.db.models import ModelCall, utc_now
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    IssueToPrEvaluation,
    IssueToPrProposal,
    IssueToPrState,
)

PlannerPurpose = Literal["issue_to_pr_patch_plan", "issue_to_pr_plan_evaluation"]


class PlannerModelCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIPlannerConfig:
    model: str
    prompt_version: str = "engineering_issue_to_pr_planner.v1"
    max_output_tokens: int = 1800


class OpenAIIssueToPrPlanner:
    def __init__(
        self,
        client: Any,
        session: Session,
        run_id: UUID,
        config: OpenAIPlannerConfig,
        trace_id: str | None = None,
    ) -> None:
        self._client = client
        self._session = session
        self._run_id = run_id
        self._config = config
        self._trace_id = trace_id

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        session: Session,
        run_id: UUID,
        config: OpenAIPlannerConfig,
        trace_id: str | None = None,
    ) -> OpenAIIssueToPrPlanner:
        return cls(
            client=AsyncOpenAI(api_key=api_key),
            session=session,
            run_id=run_id,
            config=config,
            trace_id=trace_id,
        )

    async def create_patch_plan(self, state: IssueToPrState) -> IssueToPrProposal:
        context = build_planner_context(state)
        return await self._call_structured_model(
            purpose="issue_to_pr_patch_plan",
            text_format=IssueToPrProposal,
            instructions=PATCH_PLAN_INSTRUCTIONS,
            input_payload=context,
        )

    async def evaluate_patch_plan(
        self,
        state: IssueToPrState,
        proposal: IssueToPrProposal,
    ) -> IssueToPrEvaluation:
        context = {
            "evidence": build_planner_context(state),
            "proposal": proposal.model_dump(mode="json"),
        }
        return await self._call_structured_model(
            purpose="issue_to_pr_plan_evaluation",
            text_format=IssueToPrEvaluation,
            instructions=PLAN_EVALUATION_INSTRUCTIONS,
            input_payload=context,
        )

    async def _call_structured_model[ParsedModel: BaseModel](
        self,
        purpose: PlannerPurpose,
        text_format: type[ParsedModel],
        instructions: str,
        input_payload: dict[str, Any],
    ) -> ParsedModel:
        model_call = create_model_call_record(
            run_id=self._run_id,
            model=self._config.model,
            purpose=purpose,
            prompt_version=self._config.prompt_version,
            trace_id=self._trace_id,
            input_payload=input_payload,
        )
        self._session.add(model_call)
        self._session.flush()
        started_at = perf_counter()
        try:
            response = await self._client.responses.parse(
                model=self._config.model,
                instructions=instructions,
                input=json.dumps(input_payload, sort_keys=True),
                text_format=text_format,
                max_output_tokens=self._config.max_output_tokens,
                store=False,
                metadata={
                    "run_id": str(self._run_id),
                    "purpose": purpose,
                    "prompt_version": self._config.prompt_version,
                },
            )
            parsed = parse_openai_structured_response(response, text_format)
            usage = extract_usage(response)
            model_call.status = "succeeded"
            model_call.input_token_count = usage["input_tokens"]
            model_call.output_token_count = usage["output_tokens"]
            model_call.latency_ms = int((perf_counter() - started_at) * 1000)
            model_call.completed_at = utc_now()
            model_call.response_metadata = {
                "response_id": string_or_none(getattr(response, "id", None)),
                "output_type": text_format.__name__,
            }
            self._session.flush()
            return parsed
        except Exception as exc:
            model_call.status = "failed"
            model_call.latency_ms = int((perf_counter() - started_at) * 1000)
            model_call.completed_at = utc_now()
            model_call.error_message = str(exc)
            self._session.flush()
            raise


def create_model_call_record(
    run_id: UUID,
    model: str,
    purpose: PlannerPurpose,
    prompt_version: str,
    trace_id: str | None,
    input_payload: dict[str, Any],
) -> ModelCall:
    return ModelCall(
        id=uuid4(),
        run_id=run_id,
        provider="openai",
        model=model,
        purpose=purpose,
        prompt_version=prompt_version,
        input_token_count=0,
        output_token_count=0,
        estimated_cost_usd=Decimal("0"),
        trace_id=trace_id,
        status="running",
        policy_context={"write_actions_enabled": False},
        request_metadata={
            "input_hash": hash_json_payload(input_payload),
            "input_keys": sorted(input_payload.keys()),
        },
        response_metadata={},
    )


def parse_openai_structured_response[ParsedModel: BaseModel](
    response: Any,
    text_format: type[ParsedModel],
) -> ParsedModel:
    parsed = getattr(response, "output_parsed", None)
    if isinstance(parsed, text_format):
        return parsed
    if isinstance(parsed, Mapping):
        return text_format.model_validate(parsed)
    raise PlannerModelCallError("OpenAI structured response did not include parsed output.")


def extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0}
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }


def build_planner_context(state: IssueToPrState) -> dict[str, Any]:
    issue = state["issue"]
    return {
        "workflow_id": state["workflow_id"],
        "repository": state["repository"],
        "issue": {
            "title": issue["title"],
            "body": issue["body"],
            "labels": issue.get("labels", []),
            "author": issue.get("author"),
            "url": issue["url"],
        },
        "evidence": state.get("evidence", []),
        "context_files": [
            {
                "path": file_payload["path"],
                "ref": file_payload["ref"],
                "sha": file_payload["sha"],
                "content_excerpt": excerpt(str(file_payload["content"]), 4000),
            }
            for file_payload in state.get("context_files", [])
        ],
    }


def hash_json_payload(payload: dict[str, Any]) -> str:
    import hashlib

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def excerpt(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


PATCH_PLAN_INSTRUCTIONS = """You produce source-grounded patch plans for a GitHub issue.
Use only the issue, file context, and evidence URIs provided in the input.
Do not claim branch creation, commits, pull request creation, or any write action.
Return the typed schema exactly. If evidence is insufficient, keep planned_changes minimal
and describe the missing context in risk_notes."""

PLAN_EVALUATION_INSTRUCTIONS = """Evaluate whether the proposed patch plan is grounded in the
provided GitHub evidence. Do not approve write actions. Flag missing context, risky assumptions,
and test coverage gaps. Return the typed schema exactly."""
