from __future__ import annotations

from enum import Enum
from typing import Any


class SessionState(str, Enum):
    NEW = "NEW"
    PROFILE_COLLECTING = "PROFILE_COLLECTING"
    CONSULTING = "CONSULTING"
    NEED_HUMAN = "NEED_HUMAN"
    HUMAN_TAKEN_OVER = "HUMAN_TAKEN_OVER"
    FOLLOWUP_PENDING = "FOLLOWUP_PENDING"
    CLOSED = "CLOSED"


class SessionEvent(str, Enum):
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    PROFILE_COMPLETED = "PROFILE_COMPLETED"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    RISK_DETECTED = "RISK_DETECTED"
    HANDOFF_REQUESTED = "HANDOFF_REQUESTED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    FOLLOWUP_CREATED = "FOLLOWUP_CREATED"
    SESSION_CLOSED = "SESSION_CLOSED"


TRANSITION_TABLE: dict[tuple[SessionState, SessionEvent], SessionState] = {
    (SessionState.NEW, SessionEvent.MESSAGE_RECEIVED): SessionState.PROFILE_COLLECTING,

    (SessionState.PROFILE_COLLECTING, SessionEvent.PROFILE_COMPLETED): SessionState.CONSULTING,
    (SessionState.PROFILE_COLLECTING, SessionEvent.NEED_CLARIFICATION): SessionState.PROFILE_COLLECTING,
    (SessionState.PROFILE_COLLECTING, SessionEvent.HANDOFF_REQUESTED): SessionState.NEED_HUMAN,

    (SessionState.CONSULTING, SessionEvent.MESSAGE_RECEIVED): SessionState.CONSULTING,
    (SessionState.CONSULTING, SessionEvent.NEED_CLARIFICATION): SessionState.PROFILE_COLLECTING,
    (SessionState.CONSULTING, SessionEvent.RISK_DETECTED): SessionState.NEED_HUMAN,
    (SessionState.CONSULTING, SessionEvent.HANDOFF_REQUESTED): SessionState.NEED_HUMAN,
    (SessionState.CONSULTING, SessionEvent.SESSION_CLOSED): SessionState.CLOSED,

    (SessionState.NEED_HUMAN, SessionEvent.HUMAN_ACCEPTED): SessionState.HUMAN_TAKEN_OVER,
    (SessionState.NEED_HUMAN, SessionEvent.FOLLOWUP_CREATED): SessionState.FOLLOWUP_PENDING,

    (SessionState.HUMAN_TAKEN_OVER, SessionEvent.FOLLOWUP_CREATED): SessionState.FOLLOWUP_PENDING,
    (SessionState.HUMAN_TAKEN_OVER, SessionEvent.SESSION_CLOSED): SessionState.CLOSED,

    (SessionState.FOLLOWUP_PENDING, SessionEvent.MESSAGE_RECEIVED): SessionState.CONSULTING,
    (SessionState.FOLLOWUP_PENDING, SessionEvent.SESSION_CLOSED): SessionState.CLOSED,
}


class SessionMachine:
    def __init__(self, state: str | None = None):
        raw = state or SessionState.NEW.value
        self.state = SessionState(raw)

    def transition(self, event: SessionEvent) -> SessionState:
        key = (self.state, event)
        if key in TRANSITION_TABLE:
            self.state = TRANSITION_TABLE[key]
        return self.state

    def can_receive_messages(self) -> bool:
        return self.state not in {SessionState.CLOSED}

    def is_human_active(self) -> bool:
        return self.state in {SessionState.HUMAN_TAKEN_OVER, SessionState.FOLLOWUP_PENDING}

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state.value}
