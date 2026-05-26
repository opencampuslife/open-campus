from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docling_adapter import parse_file_to_markdown
from markdown_normalizer import normalize_markdown
from compliance_precheck import compliance_precheck
from staging_store import write_staging_doc


class IngestionPipeline:

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()

    def run_ingestion(
        self,
        source_path: str,
        source_type: str,
        created_by: str,
        role: str,
        campus: str = "",
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        result: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "source_path": source_path,
            "source_type": source_type,
            "created_by": created_by,
            "role": role,
            "campus": campus,
            "staging_doc_id": "",
            "doc_id": "",
            "errors": [],
            "warnings": [],
        }

        try:
            source_file = Path(source_path)
            if not source_file.is_file():
                result["status"] = "failed"
                result["errors"].append("source file not found: {}".format(source_path))
                self._save_run(result)
                return result

            raw_bytes = source_file.read_bytes()
            source_hash = hashlib.sha256(raw_bytes).hexdigest()

            normalized = self._step_normalize(source_file, source_type)
            if normalized.get("error"):
                result["status"] = "failed"
                result["errors"].append(normalized["error"])
                self._save_run(result)
                return result

            parsed = self._step_parse(source_file, source_type)
            result["warnings"].extend(parsed.get("warnings", []))

            content = parsed.get("content", "")
            if not content and source_type in ("md", "txt"):
                content = normalized.get("content", "")

            frontmatter, body_content = self._step_extract_frontmatter(content, parsed)
            if frontmatter is None:
                result["status"] = "failed"
                result["errors"].append("failed to extract frontmatter from document")
                self._save_run(result)
                return result

            validation = self._step_validate_frontmatter(frontmatter)
            result["warnings"].extend(validation.get("warnings", []))
            if not validation.get("valid", False):
                result["status"] = "failed"
                result["errors"] = validation.get("errors", [])
                self._save_run(result)
                return result

            compliance = self._step_compliance(frontmatter, body_content)
            compliance_status = "passed" if compliance.get("passed", False) else "failed"

            staging_doc_id = write_staging_doc(self.project_root, {
                "run_id": run_id,
                "doc_id": frontmatter.get("doc_id", ""),
                "title": frontmatter.get("title", ""),
                "canonical_markdown": body_content,
                "frontmatter": frontmatter,
                "validation_status": "passed",
                "compliance_status": compliance_status,
                "review_status": "draft",
                "source_hash": source_hash,
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            result["status"] = "success"
            result["staging_doc_id"] = staging_doc_id
            result["doc_id"] = frontmatter.get("doc_id", "")
            result["compliance"] = compliance
            result["validation"] = validation

        except Exception as exc:
            result["status"] = "failed"
            result["errors"].append("pipeline error: {}".format(str(exc)))

        self._save_run(result)
        return result

    def run(
        self,
        source_path: str,
        source_type: str,
        created_by: str,
        role: str,
        campus: str = "",
    ) -> dict[str, Any]:
        return self.run_ingestion(source_path, source_type, created_by, role, campus)

    def _step_normalize(self, source_file: Path, source_type: str) -> dict[str, Any]:
        result: dict[str, Any] = {"content": "", "error": ""}
        try:
            text = source_file.read_text(encoding="utf-8", errors="replace")
            result["content"] = normalize_markdown(text)
        except Exception as exc:
            result["error"] = "normalize failed: {}".format(str(exc))
        return result

    def _step_parse(self, source_file: Path, source_type: str) -> dict[str, Any]:
        try:
            return parse_file_to_markdown(source_file)
        except Exception as exc:
            return {"content": "", "metadata": {}, "warnings": ["parse error: {}".format(str(exc))]}

    def _step_extract_frontmatter(
        self,
        content: str,
        parsed: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        from frontmatter_validator import parse_frontmatter_from_md
        md_content = content or parsed.get("content", "")
        if not md_content:
            return None, ""
        try:
            return parse_frontmatter_from_md(md_content)
        except Exception:
            pass
        if md_content.startswith("---\n"):
            try:
                parts = md_content.split("---\n", 2)
                if len(parts) >= 3:
                    fm_raw = parts[1]
                    body = parts[2].strip()
                    from frontmatter_validator import yaml_loads
                    fm = yaml_loads(fm_raw)
                    if isinstance(fm, dict):
                        return fm, body
            except Exception:
                pass
        return None, md_content

    def _step_validate_frontmatter(self, frontmatter: dict[str, Any]) -> dict[str, Any]:
        from frontmatter_validator import validate_frontmatter
        return validate_frontmatter(frontmatter, self.project_root)

    def _step_compliance(
        self,
        frontmatter: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        return compliance_precheck(frontmatter, content)

    def _save_run(self, result: dict[str, Any]) -> None:
        run_dir = self.project_root / "data" / "ingestion"
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "{}.json".format(result["run_id"])
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
