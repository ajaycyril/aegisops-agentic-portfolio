from typing import cast

from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import AuditEvent


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1


def test_write_audit_event_adds_and_flushes_record() -> None:
    recording_session = RecordingSession()
    event = AuditEventInput(
        workflow_id="engineering_issue_to_pr",
        event_type="policy_decision",
        actor_type="system",
        action="tool_access.evaluate",
        resource_type="tool",
        resource_id="github.issue.read",
        policy_decision_id="decision-123",
        trace_id="trace-123",
        payload={"allow": True},
    )

    record = write_audit_event(cast(Session, recording_session), event)

    assert isinstance(record, AuditEvent)
    assert recording_session.added == [record]
    assert recording_session.flush_count == 1
    assert record.workflow_id == "engineering_issue_to_pr"
    assert record.policy_decision_id == "decision-123"
    assert record.payload == {"allow": True}
