from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aegisops_api.db.models import AuditEvent


class AuditEventInput(BaseModel):
    run_id: UUID | None = None
    workflow_id: str | None = None
    event_type: str
    actor_type: str
    actor_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    policy_decision_id: str | None = None
    trace_id: str | None = None
    data_sensitivity: str = "internal"
    payload: dict[str, Any] = Field(default_factory=dict)


def write_audit_event(session: Session, event: AuditEventInput) -> AuditEvent:
    record = AuditEvent(
        run_id=event.run_id,
        workflow_id=event.workflow_id,
        event_type=event.event_type,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        policy_decision_id=event.policy_decision_id,
        trace_id=event.trace_id,
        data_sensitivity=event.data_sensitivity,
        payload=event.payload,
    )
    session.add(record)
    session.flush()
    return record
