from __future__ import annotations

import argparse
import sys
from pathlib import Path

KNOWLEDGE_SRC = Path(__file__).resolve().parents[1] / "services" / "knowledge-service" / "src"
sys.path.append(str(KNOWLEDGE_SRC))

from frontmatter_parser import parse_markdown  # noqa: E402
from simple_yaml import load_file  # noqa: E402
from validator import (  # noqa: E402
    check_content_prohibited,
    check_doc_id_uniqueness,
    check_public_content_leak,
    check_visibility_directory_consistency,
    validate_doc,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--check-content",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    yaml_count = 0
    for path in sorted((args.root / "configs").glob("*.yaml")):
        load_file(path)
        yaml_count += 1

    md_count = 0
    errors: list[str] = []
    doc_id_map: dict[str, str] = {}

    for path in sorted((args.root / "knowledge_vault").rglob("*.md")):
        if "metadata" in path.parts:
            continue
        metadata, body = parse_markdown(path)
        source_uri = str(path.relative_to(args.root))

        fm_errors = validate_doc(metadata, source_uri)
        dir_errors = check_visibility_directory_consistency(metadata, source_uri)
        for err in fm_errors + dir_errors:
            errors.append(f"{source_uri}: {err}")

        if args.check_content:
            content_errors = check_content_prohibited(body, metadata.get("visibility"))
            leak_errors = check_public_content_leak(metadata, body, source_uri)
            for err in content_errors + leak_errors:
                errors.append(f"{source_uri}: {err}")

        doc_id_map[metadata.get("doc_id", "")] = source_uri
        md_count += 1

    dup_errors = check_doc_id_uniqueness(doc_id_map)
    errors.extend(dup_errors)

    print(f"validated configs={yaml_count} markdown_docs={md_count}")
    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
