from __future__ import annotations

import re
from typing import Any


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def chunk_markdown(metadata: dict[str, Any], body: str, source_uri: str) -> list[dict[str, Any]]:
    tags = metadata.get("business_tags", [])
    is_faq = "FAQ" in tags or any("faq" in str(t).lower() for t in tags)

    if is_faq:
        return _chunk_faq(metadata, body, source_uri)
    return _chunk_heading(metadata, body, source_uri)


def _chunk_heading(metadata: dict[str, Any], body: str, source_uri: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_title = metadata["title"]
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if not content:
            return
        index = len(chunks) + 1
        chunk = _make_chunk(metadata, index, current_title, content, source_uri)
        chunks.append(chunk)

    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_title = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()
    return chunks


def _chunk_faq(metadata: dict[str, Any], body: str, source_uri: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_answer: list[str] = []
    has_h1: bool = True

    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            if level >= 2:
                if current_heading and current_answer:
                    answer_text = "\n".join(current_answer).strip()
                    if answer_text:
                        pairs.append((current_heading, answer_text))
                current_heading = heading_text
                current_answer = []
                if level < 2:
                    has_h1 = True
            continue
        if current_heading is not None:
            stripped = line.strip()
            if stripped:
                current_answer.append(stripped)

    if current_heading and current_answer:
        answer_text = "\n".join(current_answer).strip()
        if answer_text:
            pairs.append((current_heading, answer_text))

    for idx, (question, answer) in enumerate(pairs):
        index = idx + 1
        chunk = _make_chunk(metadata, index, question, answer, source_uri)
        chunk["question"] = question
        chunk["aliases"] = _generate_aliases(question)
        chunks.append(chunk)

    return chunks


def _generate_aliases(question: str) -> list[str]:
    aliases: list[str] = []
    alias_map = {
        "钱": ["费用", "价格", "收费", "多少钱"],
        "班": ["班型", "班级", "课程"],
        "老师": ["师资", "教师", "教学团队"],
        "住宿": ["宿舍", "寝室", "住校"],
        "手机": ["电子设备", "手机管理"],
        "报名": ["入学流程", "怎么报名", "报名条件"],
        "提分": ["成绩提升", "进步", "效果"],
        "复读": ["重新高考", "二次高考"],
        "管理": ["纪律", "规章制度"],
        "食堂": ["餐饮", "伙食", "吃饭"],
        "退费": ["退款", "休学退款"],
        "评价": ["评测", "诊断", "测试"],
        "请假": ["请假流程", "有事怎么请假"],
        "家长": ["父母", "亲人"],
        "校区": ["校园", "学校环境"],
    }
    for key, alts in alias_map.items():
        if key in question:
            aliases.extend(alts[:2])
    return aliases


def _make_chunk(
    metadata: dict[str, Any], index: int, title: str, content: str, source_uri: str
) -> dict[str, Any]:
    chunk: dict[str, Any] = {
        "chunk_id": f"{metadata['doc_id']}::chunk_{index:03d}",
        "doc_id": metadata["doc_id"],
        "title": title,
        "content": content,
        "source_uri": source_uri,
        "source_page": None,
    }
    for key in (
        "visibility",
        "allowed_roles",
        "data_level",
        "campus_scope",
        "business_tags",
        "effective_date",
        "expiry_date",
        "review_status",
        "owner",
    ):
        chunk[key] = metadata[key]
    return chunk
