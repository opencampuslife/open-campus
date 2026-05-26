from __future__ import annotations

import re
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
bt_src = str(bt_path)
if bt_src not in sys.path:
    sys.path.insert(0, bt_src)

from base import ActionNode, AgentContext, BTStatus  # noqa: E402


CRISIS_PATTERNS: dict[str, list[str]] = {
    "imminent": [
        "想死", "自杀", "结束生命", "不想活了", "死了算了",
    ],
    "high": [
        "自残", "伤害自己", "崩溃了", "撑不住", "绝望",
        "活不下去", "想不开", "世界抛弃我", "太痛苦了",
    ],
    "medium": [
        "没希望了", "没希望", "活着没意思", "不想活",
    ],
}

EMOTION_THEME_MAP: dict[str, str] = {
    "焦虑": "anxiety", "紧张": "anxiety", "担心": "anxiety",
    "压力大": "anxiety", "烦躁": "anxiety", "失眠": "anxiety",
    "睡不着": "anxiety", "比较焦虑": "anxiety", "特别紧张": "anxiety",
    "心理压力": "anxiety", "压力": "anxiety", "崩溃": "anxiety",
    "崩溃了": "anxiety", "失控": "anxiety", "发火": "anxiety",
    "不想": "anxiety", "抗拒": "anxiety", "退缩": "anxiety",
    "状态不好": "anxiety", "状态很差": "anxiety",
    "抑郁": "sadness", "难过": "sadness", "伤心": "sadness",
    "想哭": "sadness", "委屈": "sadness", "心里难受": "sadness",
    "孤单": "sadness", "压抑": "sadness", "累得不行": "sadness",
    "很累": "sadness", "心情不好": "sadness", "没人理解": "sadness",
    "不被理解": "sadness", "无人理解": "sadness",
    "害怕": "fear", "恐惧": "fear", "不敢": "fear",
    "怕刺激": "fear", "不知道怎么说": "fear",
    "拒绝": "fear", "逃避": "fear", "躲避": "fear",
    "生气": "anger", "不公平": "anger", "吵架": "anger",
    "总吵架": "anger", "摆烂": "anger",
    "内疚": "guilt", "对不起": "guilt", "辜负": "guilt",
    "后悔": "guilt", "觉得没用": "guilt", "感觉自己没用": "guilt",
    "迷茫": "confusion", "不知道怎么办": "confusion",
    "没信心": "confusion", "怀疑自己": "confusion",
    "不想上学": "confusion", "厌学": "confusion",
    "没动力": "confusion", "沉默": "confusion",
    "不想说话": "confusion", "不愿沟通": "confusion",
    "不愿": "confusion", "没办法": "confusion",
    "管不了": "confusion", "不想学": "confusion",
    "吵": "anger", "不说": "confusion", "不跟我说": "confusion",
    "不愿意说": "confusion", "没用": "guilt", "也没用": "guilt",
    "复读也没用": "guilt", "考不上": "fear", "关在房间": "avoidance",
    "不出来": "avoidance", "浪费时间": "anger", "学不会": "confusion",
    "又失败": "fear", "太丢人": "shame", "比不上": "shame",
    "不如别人": "shame", "放弃算了": "sadness", "怎么办啊": "anxiety",
    "受不了": "anxiety", "顶不住": "anxiety", "没办法了": "confusion",
    "受不了了": "anxiety", "太难受": "sadness",
    "反感": "anger", "不懂我": "confusion", "不懂": "confusion",
    "不欢而散": "anger", "怎么沟通": "confusion", "没希望": "fear",
    "不想活": "sadness",
}

EMOTION_THEME_LABELS: dict[str, str] = {
    "anxiety": "parent_anxiety",
    "sadness": "student_pressure",
    "fear": "repeat_failure_fear",
    "anger": "anger",
    "guilt": "guilt",
    "confusion": "decision_ambivalence",
    "avoidance": "avoidance",
    "shame": "shame",
}

VALIDATION_PHRASES: dict[str, list[str]] = {
    "anxiety": [
        "面对高考这么大的挑战，感到焦虑是再正常不过的。",
        "我理解你现在的紧张感——面临重要关口，几乎所有人都会有压力。",
        "焦虑其实说明你在乎这件事，这本身就是一种认真。",
    ],
    "sadness": [
        "我能感受到你现在的难受，这种情绪是完全正常的。",
        "在备考路上感觉低落是很常见的，不是你的问题。",
        "你的感受是被理解的，不是只有你一个人这样。",
    ],
    "fear": [
        "对未来感到害怕是很自然的反应，不确定性本身就会带来恐惧。",
        "我理解你害怕考不好、害怕辜负期望——这些都是很真实的感受。",
    ],
    "anger": [
        "我明白你现在很生气，这种情绪是有原因的，不是无理取闹。",
        "你有权利感到愤怒，这说明你看重公平和付出。",
    ],
    "guilt": [
        "感到内疚恰恰说明你是一个有责任感的人。",
        "把压力都揽在自己身上是很辛苦的，你已经做得很好了。",
    ],
    "confusion": [
        "现在感到迷茫是完全正常的，很多人到了这个阶段都会有同样的体验。",
        "不确定未来的方向不代表你做错了什么，只是需要时间理清。",
    ],
    "avoidance": [
        "躲避不一定是不在乎，有时候是因为害怕再次面对失望。",
        "把情绪躲开是保护自己的一种方式，可以和我说说你现在最难面对的是什么。",
    ],
    "shame": [
        "感觉丢人和被比较的痛苦是很真实的，这并不意味着你不够好。",
        "被比较的感觉确实很不好受，你的价值不取决于一次考试的结果。",
    ],
}

NORMALIZE_PHRASES: list[str] = [
    "很多学生在备考阶段都会经历类似的压力，你不是一个人。",
    "高考前有这种情绪波动的同学非常多，这是一个普遍现象。",
    "几乎每个认真备考的学生都会有这样的时刻。",
]

LOW_PRESSURE_QUESTIONS: list[str] = [
    "能和我说说，最近最让你感到压力的具体是什么吗？",
    "如果可以的话，你愿意多聊一点现在的心情吗？",
    "除了学习压力，还有什么其他事情让你觉得累？",
    "你最希望身边人怎么理解你现在的状态？",
    "如果可以和我说，是什么让你觉得这么难受？",
]

SUPPORT_STRATEGIES: dict[str, str] = {
    "anxiety": "parent_anxiety_support",
    "sadness": "student_pressure_support",
    "fear": "repeat_failure_reframe",
    "anger": "boundary_setting_support",
    "guilt": "parent_anxiety_support",
    "confusion": "motivation_support",
    "avoidance": "student_pressure_support",
    "shame": "repeat_failure_reframe",
}

STRATEGY_NAME_MAP: dict[str, str] = {
    "parent_anxiety_support": "降低焦虑，避免把焦虑转化为控制",
    "student_pressure_support": "承接学生压力，恢复可控感",
    "parent_child_conflict_support": "减少亲子互动中的防御和对抗",
    "repeat_failure_reframe": "把复读失败恐惧从人格否定转为策略问题",
    "motivation_support": "恢复学生的自我效能感",
    "boundary_setting_support": "帮助家长建立支持性边界",
}


class DetectCrisisRisk(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        message_lower = ctx.message

        for kw in CRISIS_PATTERNS["imminent"]:
            if kw in message_lower:
                ctx.crisis_risk = "imminent"
                ctx.risk_level = "high"
                ctx.handoff_triggered = True
                ctx.audit_events.append({
                    "type": "crisis_detected", "level": "imminent",
                    "keyword": kw,
                })
                ctx.answer_draft = (
                    "我感受到了你现在非常难受。你的感受很重要，也需要被认真对待。"
                    "我建议现在先找一个你信任的成年人聊一聊——可能是老师、家中的长辈，"
                    "或者拨打心理援助热线：希望24热线 400-161-9995。"
                    "我愿意在这里陪你聊，但你不需要一个人面对。"
                )
                return BTStatus.SUCCESS

        for kw in CRISIS_PATTERNS["high"]:
            if kw in message_lower:
                ctx.crisis_risk = "high"
                ctx.risk_level = "medium"
                ctx.handoff_triggered = True
                ctx.audit_events.append({
                    "type": "crisis_detected", "level": "high",
                    "keyword": kw,
                })
                ctx.answer_draft = (
                    "我能感觉到你现在承受着很大的压力，这一定很不容易。"
                    "你是否愿意和我多说说你的感受？如果你觉得需要更专业的帮助，"
                    "我建议联系学校的心理咨询老师或拨打心理援助热线。"
                )
                return BTStatus.SUCCESS

        for kw in CRISIS_PATTERNS["medium"]:
            if kw in message_lower:
                ctx.crisis_risk = "medium"
                ctx.risk_level = "medium"
                ctx.audit_events.append({
                    "type": "crisis_detected", "level": "medium",
                    "keyword": kw,
                })
                return BTStatus.FAILURE

        return BTStatus.FAILURE


class DetectEmotionSignal(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        message_lower = ctx.message
        matched_keywords: list[str] = []

        for kw, theme in EMOTION_THEME_MAP.items():
            if kw in message_lower and kw not in matched_keywords:
                matched_keywords.append(kw)

        if matched_keywords:
            ctx.emotion_signal = matched_keywords[0]
        else:
            ctx.emotion_signal = "压力"

        ctx.audit_events.append({
            "type": "emotion_signal_detected",
            "keywords": matched_keywords[:3] if matched_keywords else ["fallback"],
        })
        return BTStatus.SUCCESS


class ClassifyEmotionTheme(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        message_lower = ctx.message
        themes_found: dict[str, int] = {}

        for kw, theme in EMOTION_THEME_MAP.items():
            if kw in message_lower:
                themes_found[theme] = themes_found.get(theme, 0) + 1

        if themes_found:
            ctx.emotion_theme = max(themes_found, key=lambda k: themes_found[k])
        elif ctx.emotion_signal:
            ctx.emotion_theme = EMOTION_THEME_MAP.get(ctx.emotion_signal, "anxiety")
        else:
            ctx.emotion_theme = "anxiety"

        ctx.audit_events.append({
            "type": "emotion_theme_classified",
            "theme": ctx.emotion_theme,
            "label": EMOTION_THEME_LABELS.get(ctx.emotion_theme, "unknown"),
        })
        return BTStatus.SUCCESS


class ValidateEmotion(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        ctx.audit_events.append({
            "type": "emotion_validated",
            "theme": ctx.emotion_theme,
        })
        return BTStatus.SUCCESS


class NormalizeExperience(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        ctx.audit_events.append({
            "type": "experience_normalized",
            "theme": ctx.emotion_theme,
        })
        return BTStatus.SUCCESS


class ClarifyContext(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        return BTStatus.SUCCESS


class ReappraiseFrame(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        ctx.audit_events.append({
            "type": "frame_reappraised",
            "theme": ctx.emotion_theme,
        })
        return BTStatus.SUCCESS


class ChooseSupportStrategy(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        theme = ctx.emotion_theme or "anxiety"
        strategy = SUPPORT_STRATEGIES.get(theme, "motivation_support")
        ctx.support_strategy = strategy
        ctx.audit_events.append({
            "type": "support_strategy_chosen",
            "strategy": strategy,
            "strategy_name": STRATEGY_NAME_MAP.get(strategy, strategy),
            "theme": theme,
        })
        return BTStatus.SUCCESS


class ExecuteSupportStrategy(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        ctx.audit_events.append({
            "type": "support_strategy_executed",
            "strategy": ctx.support_strategy,
        })
        return BTStatus.SUCCESS


class AskLowPressureQuestion(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        idx = hash(ctx.message + ctx.emotion_theme) % len(LOW_PRESSURE_QUESTIONS)
        question = LOW_PRESSURE_QUESTIONS[idx]

        parts: list[str] = []
        theme = ctx.emotion_theme or "anxiety"

        validation_phrases = VALIDATION_PHRASES.get(theme, VALIDATION_PHRASES["anxiety"])
        v_idx = hash(ctx.message) % len(validation_phrases)
        parts.append(validation_phrases[v_idx])

        normalize_idx = hash(ctx.emotion_signal or ctx.message) % len(NORMALIZE_PHRASES)
        parts.append(NORMALIZE_PHRASES[normalize_idx])

        parts.append(question)

        ctx.answer_draft = "\n\n".join(parts)
        ctx.audit_events.append({
            "type": "low_pressure_response",
            "theme": theme,
            "strategy": ctx.support_strategy,
        })
        return BTStatus.SUCCESS


class OptionalAdmissionsBridge(ActionNode):
    BRIDGE_SAFE_KEYWORDS = [
        "班", "课程", "上课", "学习", "提高", "方法",
        "适合", "推荐", "怎么办", "帮忙",
    ]

    def tick(self, ctx: AgentContext) -> BTStatus:
        if ctx.crisis_risk in ("high", "imminent"):
            ctx.safe_for_bridge = False
            return BTStatus.SUCCESS

        has_admissions_signal = any(
            kw in ctx.message for kw in self.BRIDGE_SAFE_KEYWORDS
        )
        if not has_admissions_signal:
            ctx.safe_for_bridge = False
            return BTStatus.SUCCESS

        ctx.safe_for_bridge = True
        bridge_note = (
            "如果你愿意的话，等心情好一些的时候，我们可以聊聊具体的班型和备考方案。"
            "现在不用着急，按你自己的节奏来就好。"
        )
        if ctx.answer_draft:
            ctx.answer_draft = ctx.answer_draft.rstrip() + "\n\n" + bridge_note
        else:
            ctx.answer_draft = bridge_note
        ctx.audit_events.append({"type": "admissions_bridge_attempted"})
        return BTStatus.SUCCESS


class EmotionalSupportCheckCompliance(ActionNode):
    CLINICAL_TERMS = [
        r"\b诊断\b", r"\b治疗\b", r"\b用药\b", r"\b处方\b",
        r"\b病情\b", r"\b症状\b", r"\b病患者\b", r"\b心理医生\b.*治疗",
        r"\b心理咨询师\b.*治疗",
    ]

    def tick(self, ctx: AgentContext) -> BTStatus:
        if not ctx.answer_draft:
            return BTStatus.SUCCESS

        for pattern in self.CLINICAL_TERMS:
            if re.search(pattern, ctx.answer_draft):
                ctx.answer_draft = (
                    "我注意到我们的对话可能涉及到需要专业心理咨询的内容。"
                    "我是一个信息助手，不能提供临床诊断或治疗建议。"
                    "建议联系学校心理咨询老师或拨打心理援助热线获得专业帮助。"
                )
                ctx.audit_events.append({
                    "type": "clinical_boundary_enforced",
                })
                break
        return BTStatus.SUCCESS
