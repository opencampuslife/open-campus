from __future__ import annotations

from enum import Enum
from typing import Any


class EmotionalSupportState(str, Enum):
    EMOTION_DETECTED = "EMOTION_DETECTED"
    VALIDATING = "VALIDATING"
    NORMALIZING = "NORMALIZING"
    CLARIFYING = "CLARIFYING"
    REAPPRAISING = "REAPPRAISING"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"
    MOTIVATION_SUPPORT = "MOTIVATION_SUPPORT"
    BOUNDARY_SETTING = "BOUNDARY_SETTING"
    HANDOFF_RECOMMENDED = "HANDOFF_RECOMMENDED"
    CRISIS_ESCALATION = "CRISIS_ESCALATION"


class EmotionalSupportEvent(str, Enum):
    EMOTION_DETECTED = "EMOTION_DETECTED"
    CRISIS_DETECTED = "CRISIS_DETECTED"
    VALIDATED = "VALIDATED"
    NORMALIZED = "NORMALIZED"
    CLARIFIED = "CLARIFIED"
    REAPPRAISED = "REAPPRAISED"
    SOLUTION_FOUND = "SOLUTION_FOUND"
    MOTIVATED = "MOTIVATED"
    BOUNDARY_SET = "BOUNDARY_SET"
    HANDOFF_RECOMMENDED = "HANDOFF_RECOMMENDED"
    USER_RESOLVED = "USER_RESOLVED"
    BRIDGE_SAFE = "BRIDGE_SAFE"


TRANSITION_TABLE: dict[tuple[EmotionalSupportState, EmotionalSupportEvent], EmotionalSupportState] = {}

_TRANSITIONS = [
    (EmotionalSupportState.EMOTION_DETECTED, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.EMOTION_DETECTED, EmotionalSupportEvent.VALIDATED,
     EmotionalSupportState.VALIDATING),

    (EmotionalSupportState.VALIDATING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.VALIDATING, EmotionalSupportEvent.NORMALIZED,
     EmotionalSupportState.NORMALIZING),

    (EmotionalSupportState.NORMALIZING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.NORMALIZING, EmotionalSupportEvent.CLARIFIED,
     EmotionalSupportState.CLARIFYING),

    (EmotionalSupportState.CLARIFYING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.CLARIFYING, EmotionalSupportEvent.REAPPRAISED,
     EmotionalSupportState.REAPPRAISING),

    (EmotionalSupportState.REAPPRAISING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.REAPPRAISING, EmotionalSupportEvent.SOLUTION_FOUND,
     EmotionalSupportState.PROBLEM_SOLVING),

    (EmotionalSupportState.PROBLEM_SOLVING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.PROBLEM_SOLVING, EmotionalSupportEvent.MOTIVATED,
     EmotionalSupportState.MOTIVATION_SUPPORT),

    (EmotionalSupportState.MOTIVATION_SUPPORT, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.MOTIVATION_SUPPORT, EmotionalSupportEvent.BRIDGE_SAFE,
     EmotionalSupportState.BOUNDARY_SETTING),

    (EmotionalSupportState.BOUNDARY_SETTING, EmotionalSupportEvent.CRISIS_DETECTED,
     EmotionalSupportState.CRISIS_ESCALATION),
    (EmotionalSupportState.BOUNDARY_SETTING, EmotionalSupportEvent.HANDOFF_RECOMMENDED,
     EmotionalSupportState.HANDOFF_RECOMMENDED),
    (EmotionalSupportState.BOUNDARY_SETTING, EmotionalSupportEvent.USER_RESOLVED,
     EmotionalSupportState.EMOTION_DETECTED),

    (EmotionalSupportState.HANDOFF_RECOMMENDED, EmotionalSupportEvent.USER_RESOLVED,
     EmotionalSupportState.EMOTION_DETECTED),

    (EmotionalSupportState.CRISIS_ESCALATION, EmotionalSupportEvent.USER_RESOLVED,
     EmotionalSupportState.EMOTION_DETECTED),
]

for src, evt, dst in _TRANSITIONS:
    TRANSITION_TABLE[(src, evt)] = dst


class EmotionalSupportMachine:
    def __init__(self, state: str | None = None):
        raw = state or EmotionalSupportState.EMOTION_DETECTED.value
        self.state = EmotionalSupportState(raw)

    def transition(self, event: EmotionalSupportEvent) -> EmotionalSupportState:
        key = (self.state, event)
        if key in TRANSITION_TABLE:
            self.state = TRANSITION_TABLE[key]
        return self.state

    def is_crisis(self) -> bool:
        return self.state == EmotionalSupportState.CRISIS_ESCALATION

    def can_bridge_back(self) -> bool:
        return self.state in {
            EmotionalSupportState.MOTIVATION_SUPPORT,
            EmotionalSupportState.BOUNDARY_SETTING,
        }

    def requires_handoff(self) -> bool:
        return self.state == EmotionalSupportState.HANDOFF_RECOMMENDED

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state.value}
