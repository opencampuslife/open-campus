from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
nodes_path = AGENT_ROOT / "nodes"
fsm_path = AGENT_ROOT / "fsm"
sys.path.extend([str(bt_path), str(nodes_path), str(fsm_path)])

from base import AgentContext, Selector, Sequence  # noqa: E402
from emotional_support_nodes import (  # noqa: E402
    AskLowPressureQuestion,
    ChooseSupportStrategy,
    ClarifyContext,
    ClassifyEmotionTheme,
    DetectCrisisRisk,
    DetectEmotionSignal,
    EmotionalSupportCheckCompliance,
    ExecuteSupportStrategy,
    NormalizeExperience,
    OptionalAdmissionsBridge,
    ReappraiseFrame,
    ValidateEmotion,
)


def build_emotional_support_tree() -> Sequence:
    return Sequence(name="EmotionalSupportBT", children=[
        Selector(name="CrisisFirst", children=[
            DetectCrisisRisk(name="DetectCrisisRisk"),
            Sequence(name="EmotionProcessing", children=[
                DetectEmotionSignal(name="DetectEmotionSignal"),
                ClassifyEmotionTheme(name="ClassifyEmotionTheme"),
                ValidateEmotion(name="ValidateEmotion"),
                NormalizeExperience(name="NormalizeExperience"),
                ClarifyContext(name="ClarifyContext"),
                ReappraiseFrame(name="ReappraiseFrame"),
                ChooseSupportStrategy(name="ChooseSupportStrategy"),
                ExecuteSupportStrategy(name="ExecuteSupportStrategy"),
                AskLowPressureQuestion(name="AskLowPressureQuestion"),
                OptionalAdmissionsBridge(name="OptionalAdmissionsBridge"),
            ]),
        ]),

        EmotionalSupportCheckCompliance(name="EmotionalSupportCheckCompliance"),
    ])
