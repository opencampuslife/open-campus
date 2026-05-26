from __future__ import annotations

from pathlib import Path
from typing import Any

from markdown_normalizer import normalize_markdown


def is_docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except ImportError:
        return False


def parse_file_to_markdown(file_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": "",
        "metadata": {},
        "warnings": [],
    }
    try:
        ext = file_path.suffix.lower()
        if ext in (".md", ".txt"):
            raw = file_path.read_text(encoding="utf-8", errors="replace")
            result["content"] = normalize_markdown(raw)
            result["metadata"]["source"] = str(file_path)
            result["metadata"]["format"] = ext.lstrip(".")
        elif ext in (".pdf", ".docx", ".html", ".htm"):
            if not is_docling_available():
                result["content"] = ""
                result["metadata"] = {}
                result["warnings"].append(
                    "docling is not installed; cannot parse {} files".format(ext)
                )
                return result
            result = _parse_with_docling(file_path)
        else:
            result["warnings"].append("unsupported file type: {}".format(ext))
    except Exception as exc:
        result["content"] = ""
        result["metadata"] = {}
        result["warnings"].append("parse error: {}".format(str(exc)))
    return result


def _parse_with_docling(file_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": "",
        "metadata": {},
        "warnings": [],
    }
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
        converter = DocumentConverter()
        doc = converter.convert(str(file_path))
        md = doc.document.export_to_markdown()
        result["content"] = normalize_markdown(md)
        result["metadata"]["source"] = str(file_path)
        result["metadata"]["format"] = file_path.suffix.lstrip(".")
        result["metadata"]["pages"] = getattr(doc.document, "pages", None)
        result["metadata"]["docling_version"] = _docling_version()
    except Exception as exc:
        result["warnings"].append("docling parse failed: {}".format(str(exc)))
    return result


def _docling_version() -> str:
    try:
        import docling
        return getattr(docling, "__version__", "unknown")
    except ImportError:
        return "unknown"
