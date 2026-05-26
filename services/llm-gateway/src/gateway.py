from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from llm_logger import log_llm_call
from model_router import route_model
from prompt_guard import validate_llm_request
from provider_deepseek import Transport, chat_completion
from schemas import EvidenceChunk, LLMRequest


def llm_enabled() -> bool:
    return os.environ.get("DEEPSEEK_ENABLE_LLM") == "1" and bool(os.environ.get("DEEPSEEK_API_KEY"))


def generate_admissions_answer(
    *,
    project_root: Path,
    request: LLMRequest,
    transport: Transport | None = None,
) -> str | None:
    if not llm_enabled() and transport is None:
        return None

    policy_request = request.to_policy_dict()
    ok, violations = validate_llm_request(policy_request)
    if not ok:
        log_llm_call(
            project_root,
            {
                "status": "blocked",
                "blocked_by": "prompt_guard",
                "violations": violations,
                "request": policy_request,
            },
        )
        return None

    route = route_model("admissions_answer", {"role": request.user_role})
    messages = _build_messages(policy_request)
    try:
        answer = chat_completion(
            messages,
            model=route["model"],
            transport=transport,
        )
    except Exception as exc:
        log_llm_call(
            project_root,
            {
                "status": "error",
                "route": route,
                "error": str(exc),
                "request": policy_request,
            },
        )
        return None

    log_llm_call(
        project_root,
        {
            "status": "ok",
            "route": route,
            "request": policy_request,
            "answer": answer,
        },
    )
    return answer


def _build_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    scope = request["scope"]
    system = (
        "你是复读学校招生问答 Agent。只能使用提供的 allowed evidence 回答。"
        "不要编造政策、价格、名额或录取结果。不得承诺固定提分或保证录取。"
        "如果角色是 visitor/student/parent，不得输出 internal/L3/L4 内容。"
        "如果角色是 sales 且证据含 internal 内容，必须标注“内部参考”，并提醒不要原样对外发送。"
        "回答末尾用“来源：”列出证据标题。"
    )
    user = (
        f"用户角色：{scope['role']}\n"
        f"校区：{scope.get('campus')}\n"
        f"意图：{request['intent']}\n"
        f"用户问题：{request['message']}\n"
        f"allowed evidence：{request['evidence']}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _clean_chunk(content: str) -> str:
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            lines.append(stripped)
    return " ".join(lines)
