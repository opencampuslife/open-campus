#!/usr/bin/env python3
"""Inventory Python runtime dependencies across services/*.

Scans each service's src/ for imports, classifies them (stdlib / local / third-party),
maps third-party imports to pip package names, and outputs a JSON report.

Does NOT modify service pyproject.toml or generate uv.lock.

Usage:
    python tools/inventory_python_dependencies.py --root . [--output reports/python_dependency_inventory.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE
)

# Third-party import name -> pip package name mapping.
# None means the import is handled by a different package or is ambiguous.
THIRD_PARTY_MAP: dict[str, str | None] = {
    # AI / ML / LLM
    "docling": "docling",
    "torch": "torch",
    "transformers": "transformers",
    "sentence_transformers": "sentence-transformers",
    "openai": "openai",
    "tiktoken": "tiktoken",
    "langchain": "langchain",
    "chromadb": "chromadb",
    # Web frameworks
    "fastapi": "fastapi",
    "flask": "flask",
    "uvicorn": "uvicorn",
    "starlette": "starlette",
    "aiohttp": "aiohttp",
    "httpx": "httpx",
    "requests": "requests",
    "urllib3": "urllib3",
    "websockets": "websockets",
    "sseclient": "sseclient-py",
    # Database
    "psycopg": "psycopg[binary]",
    "psycopg2": "psycopg2-binary",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "redis": "redis",
    "pymongo": "pymongo",
    "asyncpg": "asyncpg",
    "pgvector": "pgvector",
    # Data / config
    "yaml": "pyyaml",
    "PIL": "pillow",
    "cv2": "opencv-python-headless",
    "numpy": "numpy",
    "pandas": "pandas",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "dotenv": "python-dotenv",
    "tomli": "tomli",
    "tomli_w": "tomli-w",
    "orjson": "orjson",
    "ujson": "ujson",
    # Auth / Security
    "jwt": "pyjwt",
    "cryptography": "cryptography",
    "passlib": "passlib",
    "bcrypt": "bcrypt",
    "jose": "python-jose",
    # CLI / logging / tools
    "click": "click",
    "rich": "rich",
    "tqdm": "tqdm",
    "loguru": "loguru",
    "pytest": "pytest",
    # Serialization
    "msgpack": "msgpack",
    "protobuf": "protobuf",
    # Cloud
    "boto3": "boto3",
    # OCR
    "pytesseract": "pytesseract",
    "easyocr": "easyocr",
    # Network / TLS
    "certifi": "certifi",
    "websocket": "websocket-client",
    # Templating / docs
    "jinja2": "jinja2",
    "markdown": "markdown",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    # Task queues
    "celery": "celery",
    # MCP
    "mcp": "mcp",
    "fastmcp": "fastmcp",
    # Resilience
    "tenacity": "tenacity",
    # Crypto
    "Crypto": "pycryptodome",
}


@dataclass
class ServiceDeps:
    name: str
    imports_stdlib: set[str] = field(default_factory=set)
    imports_local: set[str] = field(default_factory=set)
    imports_third_party: dict[str, str | None] = field(default_factory=dict)
    imports_unknown: set[str] = field(default_factory=set)
    file_count: int = 0
    skipped_files: int = 0


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def build_stdlib_set() -> set[str]:
    return {
        m.split(".")[0] for m in sys.stdlib_module_names
    }


def build_local_module_index(root: Path) -> set[str]:
    """Find all local Python module names discoverable in the services/ tree."""
    names: set[str] = set()
    services_dir = root / "services"
    if not services_dir.is_dir():
        return names

    for py_file in services_dir.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        names.add(py_file.stem)

    # Also add directories under src/ (Python 3.3+ implicit namespace packages)
    for src_dir in services_dir.glob("*/src"):
        for child in src_dir.iterdir():
            if child.is_dir():
                names.add(child.name)

    return names


def scan_service_imports(
    svc_dir: Path, stdlib: set[str], local_modules: set[str]
) -> ServiceDeps:
    name = svc_dir.name
    deps = ServiceDeps(name=name)
    src_dir = svc_dir / "src"
    if not src_dir.is_dir():
        return deps

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name.startswith("__"):
            continue
        deps.file_count += 1
        try:
            text = _read_file(py_file)
        except Exception:
            deps.skipped_files += 1
            continue

        for m in IMPORT_RE.finditer(text):
            top = m.group(1).split(".")[0]
            if not top:
                continue
            if top in stdlib:
                deps.imports_stdlib.add(top)
            elif top in THIRD_PARTY_MAP:
                deps.imports_third_party[top] = THIRD_PARTY_MAP[top]
            elif top in local_modules:
                deps.imports_local.add(top)
            else:
                deps.imports_unknown.add(top)

    return deps


def deps_to_entry(deps: ServiceDeps) -> dict:
    stdlib = sorted(deps.imports_stdlib)
    local = sorted(deps.imports_local)
    third_party = {
        imp: pkg for imp, pkg in sorted(deps.imports_third_party.items())
    }
    unknown = sorted(deps.imports_unknown)

    # suggested_dependencies: only third-party with known pip mapping
    suggested = sorted(
        pkg for pkg in third_party.values() if pkg is not None
    )

    # unmapped: third-party imports with None mapping + unknown
    unmapped_third = sorted(
        imp for imp, pkg in third_party.items() if pkg is None
    )

    # Overall confidence:
    # high   = no unknowns, no unmapped third-party
    # medium = some unknowns but all third-party mapped
    # low    = unmapped third-party imports
    if unknown or unmapped_third:
        confidence = "low"
    elif any(third_party.values()):
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "name": deps.name,
        "file_count": deps.file_count,
        "skipped_files": deps.skipped_files,
        "imports_stdlib": stdlib,
        "imports_local": local,
        "imports_third_party": third_party,
        "imports_unknown": unknown,
        "suggested_dependencies": suggested,
        "unmapped_third_party": unmapped_third,
        "confidence": confidence,
    }


def compute_summary(entries: list[dict]) -> dict:
    python_svcs = [e for e in entries if e["file_count"] > 0]
    total = len(python_svcs)

    # Collect all suggested dependencies across services (deduped)
    all_deps: set[str] = set()
    for e in python_svcs:
        all_deps.update(e["suggested_dependencies"])

    # Services that would need pip packages beyond the current CI baseline
    ci_baseline = {"ruff", "mypy", "psycopg[binary]", "pyyaml", "certifi"}
    new_deps = all_deps - ci_baseline

    # Confidence distribution
    by_confidence: dict[str, int] = defaultdict(int)
    for e in python_svcs:
        by_confidence[e["confidence"]] += 1

    # Services with unknown imports
    has_unknown = [
        e["name"] for e in python_svcs if e["imports_unknown"]
    ]
    has_unmapped = [
        e["name"] for e in python_svcs if e["unmapped_third_party"]
    ]

    return {
        "python_services_scanned": total,
        "total_suggested_dependencies": len(all_deps),
        "ci_baseline_deps": sorted(ci_baseline),
        "new_deps_beyond_ci_baseline": sorted(new_deps),
        "confidence_distribution": dict(by_confidence),
        "services_with_unknown_imports": has_unknown,
        "services_with_unmapped_third_party": has_unmapped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inventory Python runtime dependency imports"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--output", type=Path, help="Path to write JSON output")
    parser.add_argument("--summary-only", action="store_true", help="Print summary only")
    args = parser.parse_args()

    root = args.root.resolve()
    services_dir = root / "services"
    if not services_dir.is_dir():
        print(f"ERROR: services/ not found under {root}", file=sys.stderr)
        sys.exit(2)

    stdlib = build_stdlib_set()
    local_modules = build_local_module_index(root)

    entries: list[dict] = []
    for svc_dir in sorted(services_dir.iterdir()):
        if not svc_dir.is_dir():
            continue
        name = svc_dir.name
        if name == "uploads":
            continue
        is_python = (svc_dir / "src").is_dir() and not (svc_dir / "package.json").exists()
        if not is_python:
            continue

        deps = scan_service_imports(svc_dir, stdlib, local_modules)
        entries.append(deps_to_entry(deps))

    summary = compute_summary(entries)
    report = {
        "schema_version": 1,
        "root": str(root),
        "stdlib_module_count": len(stdlib),
        "local_module_count": len(local_modules),
        "summary": summary,
        "services": entries,
    }

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_text, encoding="utf-8")
        print(f"Dependency inventory written to {args.output}")
    else:
        print(json_text)

    if args.summary_only:
        import pprint
        pprint.pprint(summary)


if __name__ == "__main__":
    main()
