from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from loader import load_knowledge


def build_index(project_root: Path, *, strict: bool = True) -> dict[str, object]:
    docs, chunks, errors = load_knowledge(project_root / "knowledge_vault", strict=strict)
    if errors:
        for err in errors:
            print(f"WARNING: {err}", file=sys.stderr)
    index = {"docs": docs, "chunks": chunks}
    out_dir = project_root / "data" / "indexes"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "knowledge_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--strict", action="store_true", default=True)
    args = parser.parse_args()
    index = build_index(args.root, strict=args.strict)
    print(f"indexed docs={len(index['docs'])} chunks={len(index['chunks'])}")


if __name__ == "__main__":
    main()
