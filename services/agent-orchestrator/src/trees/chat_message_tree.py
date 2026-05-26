from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
nodes_path = AGENT_ROOT / "nodes"
fsm_path = AGENT_ROOT / "fsm"
consultation_path = AGENT_ROOT / "consultation"
trees_path = AGENT_ROOT / "trees"
sys.path.extend([str(AGENT_ROOT), str(bt_path), str(nodes_path), str(fsm_path), str(consultation_path), str(trees_path)])

from base import AgentContext, Node, Selector, Sequence  # noqa: E402
from machine import SessionState  # noqa: E402
from consultation_answer import GenerateConsultationAnswer  # noqa: E402
from consultation_stage import DetermineConsultationStage  # noqa: E402
from recommendation_routing import ClassRecommendationRouting  # noqa: E402
from pipeline_nodes import (  # noqa: E402
    BuildPermissionScope,
    CheckCompliance,
    ClassifyIntent,
    DetectEmotionalMode,
    DetectPromiseSeeking,
    DetectPromptInjection,
    ExtractProfile,
    FinalizeAnswer,
    GenerateAnswer,
    HasEvidence,
    NoEvidenceFallback,
    RetrieveEvidence,
    RewriteQuery,
    WriteAudit,
)
from emotional_support_tree import build_emotional_support_tree  # noqa: E402


def build_tree_for_state(state: SessionState, ctx: AgentContext) -> Node:
    if state in {SessionState.CLOSED}:
        return _closed_tree()
    return _default_chat_tree()


def _default_chat_tree() -> Sequence:
    return Sequence(name="ChatMessageBT", children=[
        BuildPermissionScope(name="BuildPermissionScope"),

        Selector(name="SafetyRouting", children=[
            DetectPromptInjection(name="DetectPromptInjection"),
            DetectPromiseSeeking(name="DetectPromiseSeeking"),
            Sequence(name="ContinueOnSafe", children=[
                ClassifyIntent(name="ClassifyIntent"),
                ExtractProfile(name="ExtractProfile"),
                DetermineConsultationStage(name="DetermineConsultationStage"),
                RewriteQuery(name="RewriteQuery"),
                RetrieveEvidence(name="RetrieveEvidence"),
                Selector(name="ModeRouting", children=[
                    Sequence(name="EmotionalSupportMode", children=[
                        DetectEmotionalMode(name="DetectEmotionalMode"),
                        build_emotional_support_tree(),
                    ]),
                    Sequence(name="AdmissionsConsultationMode", children=[
                        Selector(name="AnswerRouting", children=[
                            Sequence(name="ConsultationPolicyAnswer", children=[
                                ClassRecommendationRouting(name="ClassRecommendationRouting"),
                                GenerateConsultationAnswer(name="GenerateConsultationAnswer"),
                            ]),
                            Sequence(name="EvidenceAnswer", children=[
                                HasEvidence(name="HasEvidence"),
                                GenerateAnswer(name="GenerateAnswer"),
                            ]),
                            NoEvidenceFallback(name="NoEvidenceFallback"),
                        ]),
                    ]),
                ]),
            ]),
        ]),

        CheckCompliance(name="CheckCompliance"),
        FinalizeAnswer(name="FinalizeAnswer"),
        WriteAudit(name="WriteAudit"),
    ])


def _closed_tree() -> Sequence:
    return Sequence(name="ClosedBT", children=[
        BuildPermissionScope(),
    ])
