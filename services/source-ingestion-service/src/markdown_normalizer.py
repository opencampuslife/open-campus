from __future__ import annotations

import re


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        cleaned.append(line.rstrip())
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^#{1,6}(?=\S)", lambda m: m.group(0) + " ", text, flags=re.MULTILINE)
    text = text.rstrip("\n") + "\n"
    return text
