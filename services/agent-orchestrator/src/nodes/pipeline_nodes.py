from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
bt_src = str(bt_path)
if bt_src not in sys.path:
    sys.path.insert(0, bt_src)

SERVICES_ROOT = Path(__file__).resolve().parents[4]
PERMISSION_SRC = SERVICES_ROOT / "services" / "permission-service" / "src"
RAG_SRC = SERVICES_ROOT / "services" / "rag-service" / "src"
LLM_SRC = SERVICES_ROOT / "services" / "llm-gateway" / "src"
CRM_SRC = SERVICES_ROOT / "services" / "crm-service" / "src"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
sys.path.extend([str(PERMISSION_SRC), str(RAG_SRC), str(LLM_SRC), str(CRM_SRC)])

from base import ActionNode, AgentContext, BTStatus, ConditionNode  # noqa: E402


class BuildPermissionScope(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from scope_builder import build_scope
        identity = {
            "user_id": ctx.user_id,
            "role": ctx.role,
            "campus": ctx.campus,
            "auth_level": ctx.auth_level,
        }
        ctx.permission_scope = build_scope(identity, ctx.project_root)
        return BTStatus.SUCCESS


class DetectPromptInjection(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from prompt_guard import validate_llm_request
        ok, violations = validate_llm_request({
            "task": "admissions_answer",
            "message": ctx.message,
            "intent": ctx.intent or "faq",
            "scope": {"role": ctx.role, "campus": ctx.campus},
            "evidence": [],
        })
        if not ok:
            ctx.risk_level = "high"
            ctx.audit_events.append({
                "type": "prompt_injection_blocked",
                "violations": violations,
            })
            ctx.answer_draft = "我暂时无法处理这个请求。如有需要，请描述您的实际咨询需求。"
            return BTStatus.SUCCESS
        return BTStatus.FAILURE


class DetectPromiseSeeking(ActionNode):
    PROMISE_PATTERNS = ["保证提分", "保证录取", "一定上本科", "一定能冲", "包过", "包录取"]

    def tick(self, ctx: AgentContext) -> BTStatus:
        if ctx.role not in {"sales", "admin"}:
            for phrase in self.PROMISE_PATTERNS:
                if phrase in ctx.message:
                    ctx.answer_draft = (
                        "不能承诺固定提分或录取结果。提分效果取决于学生基础、学习周期、"
                        "执行力和弱科情况。学校通过分层教学、阶段检测和班主任跟踪管理"
                        "帮助学生提升学习效率。如有需要，可以预约学情评估了解具体方案。"
                    )
                    ctx.audit_events.append({
                        "type": "promise_seeking_blocked",
                        "phrase": phrase,
                    })
                    return BTStatus.SUCCESS
        return BTStatus.FAILURE


class ClassifyIntent(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from intent_classifier import classify_intent
        result = classify_intent(ctx.message)
        ctx.intent = result["intent"]
        ctx.intent_detail = result
        return BTStatus.SUCCESS


class RewriteQuery(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from query_rewriter import expand_query
        ctx.normalized_message = expand_query(ctx.message, ctx.intent)
        return BTStatus.SUCCESS


class RetrieveEvidence(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from search_router import search_knowledge
        source = os.environ.get("RAG_SOURCE")
        result = search_knowledge(
            ctx.normalized_message or ctx.message,
            ctx.permission_scope,
            ctx.project_root,
            entrypoint=ctx.entrypoint,
            force_source=source or None,
        )
        ctx.allowed_chunks = result.get("allowed_chunks", [])
        ctx.denied_chunks = result.get("denied_pre_filter", [])
        ctx.citations = result.get("citations", [])
        return BTStatus.SUCCESS


class HasEvidence(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        if ctx.allowed_chunks:
            return BTStatus.SUCCESS
        return BTStatus.FAILURE


class NoEvidenceFallback(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        if ctx.intent in ("promise_risk",):
            ctx.answer_draft = (
                "不能承诺固定提分或录取结果。提分效果取决于学生基础、学习周期、"
                "执行力和弱科情况。学校通过分层教学、阶段检测和班主任跟踪管理"
                "帮助学生提升学习效率。\n\n来源：测评准备"
            )
        elif ctx.intent in ("pricing_consulting",):
            ctx.answer_draft = (
                "关于费用，可以按公开口径说明：学费会根据校区、班型、课程周期和学生学情"
                "安排有所差异。\n\n具体费用建议预约顾问结合学生情况确认。\n\n来源：公开费用说明"
            )
        elif ctx.intent in ("complaint",):
            ctx.answer_draft = (
                "非常理解您的心情。建议您留下联系方式，我们会安排相关负责人"
                "第一时间与您沟通处理。"
            )
        else:
            ctx.answer_draft = (
                "我暂时没有检索到当前身份可访问的已审核资料。"
                "建议补充校区、班型或咨询目标，或转人工顾问确认。"
            )
        return BTStatus.SUCCESS


class GenerateAnswer(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from answer_generator import generate_answer
        retrieval = {
            "allowed_chunks": ctx.allowed_chunks,
            "denied_pre_filter": ctx.denied_chunks,
            "citations": ctx.citations,
        }
        ctx.answer_draft = generate_answer(
            ctx.message,
            retrieval,
            ctx.intent,
            ctx.permission_scope,
            ctx.project_root,
        )
        return BTStatus.SUCCESS


class CheckCompliance(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from compliance_gate import check_answer, safe_rewrite
        checked = check_answer(ctx.answer_draft, ctx.permission_scope, ctx.project_root)
        ctx.compliance_passed = checked["passed"]
        ctx.compliance_violations = checked.get("violations", [])
        if not ctx.compliance_passed:
            ctx.answer_draft = safe_rewrite(ctx.answer_draft, ctx.compliance_violations)
        return BTStatus.SUCCESS


class FinalizeAnswer(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        ctx.answer_final = ctx.answer_draft
        return BTStatus.SUCCESS


class WriteAudit(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from audit_logger import audit_log
        event = {
            "user_id": ctx.user_id,
            "role": ctx.role,
            "campus": ctx.campus,
            "entrypoint": ctx.entrypoint,
            "message": ctx.message,
            "intent": ctx.intent_detail,
            "retrieved_chunk_ids": [c.get("chunk_id") for c in ctx.allowed_chunks],
            "denied_pre_filter": ctx.denied_chunks,
            "compliance": {
                "passed": ctx.compliance_passed,
                "violations": ctx.compliance_violations,
            },
            "answer": ctx.answer_final,
            "bt_nodes": ctx.audit_events,
        }
        audit_log(ctx.project_root, event)
        return BTStatus.SUCCESS


class ExtractProfile(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from profile_model import extract_profile_from_message, merge_profile, compute_completeness
        from profile_merge_policy import apply_merge_policy, detect_corrections, update_profile_meta

        corrections = detect_corrections(ctx.message)
        patch = extract_profile_from_message(ctx.message, ctx.profile)

        existing_meta = ctx.profile.get("_meta", {})
        merged, decisions, warnings = apply_merge_policy(
            ctx.profile, patch.updates, patch.confidence,
            existing_meta=existing_meta, corrections=corrections,
        )

        merged["_meta"] = update_profile_meta(
            existing_meta, patch.updates, patch.confidence,
            decisions, evidence=ctx.message[:200],
        )

        ctx.profile = merged
        ctx.profile_completeness = compute_completeness(merged)
        ctx.profile_missing_fields = [f for f in ["subject_type", "current_score", "target_school_level"] if not merged.get(f)]
        ctx.profile_merge_decisions = [{"field": d.field, "action": d.action, "reason": d.reason} for d in decisions]
        ctx.profile_needs_confirmation = [d for d in decisions if d.action == "needs_confirmation"]

        if patch.updates or corrections:
            ctx.audit_events.append({
                "type": "profile_updated",
                "updated_fields": sorted(patch.updates.keys()),
                "corrections": len(corrections),
                "decisions": ctx.profile_merge_decisions,
            })
        return BTStatus.SUCCESS


class DetectEmotionalMode(ConditionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from mode_router import route_mode
        mode = route_mode(ctx.message, ctx.intent)
        if mode == "emotional_support":
            ctx.active_mode = mode
            ctx.audit_events.append({"type": "mode_routed", "mode": mode})
            return BTStatus.SUCCESS
        return BTStatus.FAILURE
