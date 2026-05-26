from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

AGENT_SRC = Path(__file__).resolve().parent
sys.path.extend([str(AGENT_SRC)])

sys.path.insert(0, str(AGENT_SRC / "bt"))
sys.path.insert(0, str(AGENT_SRC / "fsm"))
sys.path.insert(0, str(AGENT_SRC / "trees"))

PERMISSION_SRC = Path(__file__).resolve().parents[2] / "permission-service" / "src"
RAG_SRC = Path(__file__).resolve().parents[2] / "rag-service" / "src"
KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.extend([str(PERMISSION_SRC), str(RAG_SRC), str(KNOWLEDGE_SRC)])

from base import AgentContext, run_tree  # noqa: E402
from chat_message_tree import build_tree_for_state  # noqa: E402
from machine import SessionEvent, SessionMachine, SessionState  # noqa: E402


USE_BT = True


def receive_message(
    identity: dict[str, Any],
    message: str,
    project_root: Path,
    *,
    entrypoint: str = "public_chat",
    retrieval_source: str | None = None,
    initial_profile: dict[str, Any] | None = None,
    initial_recommendation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if USE_BT:
        return _receive_bt(
            identity,
            message,
            project_root,
            entrypoint,
            retrieval_source,
            initial_profile,
            initial_recommendation,
        )
    return _receive_legacy(identity, message, project_root, entrypoint, retrieval_source)


def _receive_bt(
    identity: dict[str, Any],
    message: str,
    project_root: Path,
    entrypoint: str = "public_chat",
    retrieval_source: str | None = None,
    initial_profile: dict[str, Any] | None = None,
    initial_recommendation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = AgentContext(
        user_id=str(identity.get("user_id", "anonymous")),
        role=str(identity.get("role", "visitor")),
        campus=str(identity.get("campus", "all")),
        auth_level=str(identity.get("auth_level", "anonymous")),
        entrypoint=entrypoint,
        message=message,
        profile=dict(initial_profile or {}),
        recommendation_result=dict(initial_recommendation) if initial_recommendation else None,
        project_root=project_root,
    )

    fsm = SessionMachine(SessionState.CONSULTING.value)
    ctx.fsm_state = fsm.state.value
    tree = build_tree_for_state(fsm.state, ctx)
    result = run_tree(tree, ctx)

    if result.ok:
        fsm.transition(SessionEvent.MESSAGE_RECEIVED)
    else:
        fsm.transition(SessionEvent.RISK_DETECTED)

    return result.response


def _receive_legacy(
    identity: dict[str, Any],
    message: str,
    project_root: Path,
    entrypoint: str = "public_chat",
    retrieval_source: str | None = None,
) -> dict[str, Any]:

    from audit_logger import audit_log
    from compliance_gate import check_answer, safe_rewrite
    from intent_classifier import classify_intent
    from scope_builder import build_scope
    from search_router import search_knowledge
    from answer_generator import generate_answer

    scope = build_scope(identity, project_root)
    intent = classify_intent(message)
    retrieval = search_knowledge(
        message,
        scope,
        project_root,
        entrypoint=entrypoint,
        force_source=retrieval_source,
    )
    answer = generate_answer(message, retrieval, str(intent["intent"]), scope, project_root)
    compliance = check_answer(answer, scope, project_root)
    if not compliance["passed"]:
        answer = safe_rewrite(answer, compliance["violations"])

    event = {
        "user_id": identity.get("user_id"),
        "role": scope["role"],
        "campus": scope["campus"],
        "entrypoint": entrypoint,
        "message": message,
        "intent": intent,
        "retrieved_chunk_ids": [c["chunk_id"] for c in retrieval["allowed_chunks"]],
        "denied_pre_filter": retrieval["denied_pre_filter"],
        "compliance": compliance,
        "answer": answer,
    }
    audit_log(project_root, event)
    return {
        "answer": answer,
        "intent": intent,
        "retrieval": retrieval,
        "compliance": compliance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--identity", required=True, help="JSON identity")
    parser.add_argument("--message", required=True)
    parser.add_argument("--entrypoint", default="public_chat")
    parser.add_argument("--retrieval-source", choices=["json", "postgres"], default=None)
    args = parser.parse_args()
    result = receive_message(
        json.loads(args.identity),
        args.message,
        args.root,
        entrypoint=args.entrypoint,
        retrieval_source=args.retrieval_source,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
