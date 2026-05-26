#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / ".codegraph" / "codegraph.db"
DEFAULT_OUT_PATH = REPO_ROOT / "docs" / "codegraph.html"
DEFAULT_INCLUDE_ALL_FILES = True


@dataclass(frozen=True)
class ProtocolHit:
    protocol: str
    pattern: str
    line: int
    snippet: str


PROTOCOL_RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "HTTP Server",
        [
            re.compile(r"\bFastAPI\s*\(", re.I),
            re.compile(r"\bAPIRouter\s*\(", re.I),
            re.compile(r"@\w+\.(get|post|put|patch|delete)\b", re.I),
            re.compile(r"\bFlask\s*\(", re.I),
            re.compile(r"\bBlueprint\s*\(", re.I),
            re.compile(r"\bHTTPServer\b", re.I),
            re.compile(r"\bBaseHTTPRequestHandler\b", re.I),
        ],
    ),
    (
        "HTTP Client",
        [
            re.compile(r"\brequests\.(get|post|put|patch|delete)\b", re.I),
            re.compile(r"\bhttpx\.(get|post|put|patch|delete)\b", re.I),
            re.compile(r"\baiohttp\b", re.I),
            re.compile(r"\burllib\.request\b", re.I),
        ],
    ),
    (
        "WebSocket",
        [
            re.compile(r"\bWebSocket\b", re.I),
            re.compile(r"\bwebsockets\b", re.I),
            re.compile(r"\bws://", re.I),
            re.compile(r"\bwss://", re.I),
            re.compile(r"\bsocketio\b", re.I),
        ],
    ),
    (
        "gRPC",
        [
            re.compile(r"\bgrpc\b", re.I),
            re.compile(r"\.proto\b", re.I),
        ],
    ),
    (
        "MCP (Model Context Protocol)",
        [
            re.compile(r"\bmodelcontextprotocol\b", re.I),
            re.compile(r"\bmcp\b", re.I),
            re.compile(r"\bCallToolRequestSchema\b", re.I),
            re.compile(r"\bListToolsRequestSchema\b", re.I),
        ],
    ),
    (
        "Database (SQL)",
        [
            re.compile(r"\bpostgres\b", re.I),
            re.compile(r"\bpsycopg\b", re.I),
            re.compile(r"\basyncpg\b", re.I),
            re.compile(r"\bsqlite3\b", re.I),
            re.compile(r"\bmysql\b", re.I),
            re.compile(r"\bsqlalchemy\b", re.I),
            re.compile(r"\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b", re.I),
        ],
    ),
    (
        "Redis",
        [
            re.compile(r"\bredis\b", re.I),
        ],
    ),
    (
        "Message Queue",
        [
            re.compile(r"\bcelery\b", re.I),
            re.compile(r"\brabbitmq\b", re.I),
            re.compile(r"\bamqp\b", re.I),
            re.compile(r"\bpika\b", re.I),
            re.compile(r"\baio_pika\b", re.I),
            re.compile(r"\bkafka\b", re.I),
            re.compile(r"\bnats\b", re.I),
        ],
    ),
]


GROUP_SPECS: list[dict[str, str]] = [
    {
        "id": "admin_console",
        "title": "Admin Console Agent",
        "description": "后台前端、管理页与运营入口。",
        "color": "#22c55e",
    },
    {
        "id": "campus_ops",
        "title": "Campus Ops Agent",
        "description": "校园事务主链路：网关、鉴权、流程、订餐、企微桥接。",
        "color": "#38bdf8",
    },
    {
        "id": "knowledge_stack",
        "title": "Knowledge Agent",
        "description": "RAG、LLM 路由、知识图谱、内容接入与评测。",
        "color": "#f59e0b",
    },
    {
        "id": "crm_growth",
        "title": "CRM Agent",
        "description": "招生线索、画像、交接与 next-best-action。",
        "color": "#f472b6",
    },
    {
        "id": "policy_security",
        "title": "Policy & Security Agent",
        "description": "权限、RLS、合规与策略控制。",
        "color": "#a78bfa",
    },
    {
        "id": "shared_assets",
        "title": "Shared Assets Agent",
        "description": "共享类型、配置、SQL 夹具与跨模块基础资产。",
        "color": "#14b8a6",
    },
    {
        "id": "quality_ops",
        "title": "Quality Ops Agent",
        "description": "测试、运维脚本、发布检查与运行文档。",
        "color": "#fb7185",
    },
    {
        "id": "other",
        "title": "Other Agent",
        "description": "暂未细分到主要功能域的文件。",
        "color": "#94a3b8",
    },
]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _iter_rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> Iterable[sqlite3.Row]:
    cur = conn.execute(sql, tuple(params))
    for row in cur:
        yield row


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    except FileNotFoundError:
        return None


def detect_protocols(file_path: Path, max_hits_per_protocol: int = 10) -> list[ProtocolHit]:
    text = _read_text(file_path)
    if text is None:
        return []

    hits: list[ProtocolHit] = []
    lines = text.splitlines()
    for protocol, patterns in PROTOCOL_RULES:
        per_protocol = 0
        for idx, line in enumerate(lines, start=1):
            if per_protocol >= max_hits_per_protocol:
                break
            for pat in patterns:
                if pat.search(line):
                    snippet = line.strip()
                    snippet = snippet[:240]
                    hits.append(ProtocolHit(protocol=protocol, pattern=pat.pattern, line=idx, snippet=snippet))
                    per_protocol += 1
                    break
    return hits


def build_graph(db_path: Path, repo_root: Path) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        files = list(
            _iter_rows(
                conn,
                """
                select path, language, size, modified_at, indexed_at, node_count, errors
                from files
                order by path asc
                """,
            )
        )
        nodes = list(
            _iter_rows(
                conn,
                """
                select
                    id, kind, name, qualified_name, file_path, language,
                    start_line, end_line, start_column, end_column,
                    docstring, signature, decorators, visibility,
                    is_exported, is_async, is_static, is_abstract,
                    updated_at
                from nodes
                order by file_path asc, start_line asc, start_column asc
                """,
            )
        )
        edges = list(
            _iter_rows(
                conn,
                """
                select source, target, kind, metadata, line, col, provenance
                from edges
                """,
            )
        )
    finally:
        conn.close()

    file_meta: dict[str, dict[str, Any]] = {f["path"]: dict(f) for f in files}

    protocol_cache: dict[str, list[ProtocolHit]] = {}
    file_protocol_summary: dict[str, dict[str, Any]] = {}
    for path in file_meta.keys():
        abs_path = repo_root / path
        hits = detect_protocols(abs_path)
        protocol_cache[path] = hits
        by_proto: dict[str, list[dict[str, Any]]] = {}
        for h in hits:
            by_proto.setdefault(h.protocol, []).append(
                {"line": h.line, "snippet": h.snippet, "pattern": h.pattern}
            )
        file_protocol_summary[path] = {
            "protocols": sorted(by_proto.keys()),
            "evidence": by_proto,
        }

    out_nodes: list[dict[str, Any]] = []
    for n in nodes:
        d = dict(n)
        fp = d.get("file_path")
        if fp in file_protocol_summary:
            d["protocols"] = file_protocol_summary[fp]["protocols"]
        out_nodes.append(d)

    out_edges = [dict(e) for e in edges]

    graph = {
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "db_path": str(db_path),
        "files": file_meta,
        "file_protocols": file_protocol_summary,
        "nodes": out_nodes,
        "edges": out_edges,
    }
    return graph


def _iter_repo_files(repo_root: Path, include_exts: set[str], exclude_dirs: set[str]) -> list[str]:
    out: list[str] = []
    for root, dirs, files in os.walk(repo_root):
        rel_root = Path(root).resolve().relative_to(repo_root)
        if set(rel_root.parts) & exclude_dirs:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fn in files:
            p = Path(root) / fn
            if p.suffix.lower() not in include_exts:
                continue
            rel = p.resolve().relative_to(repo_root)
            if rel.parts and rel.parts[0] in exclude_dirs:
                continue
            out.append(str(rel).replace("\\", "/"))
    return sorted(set(out))


def _resolve_python_module(repo_root: Path, base_dir: Path, module: str) -> set[str]:
    out: set[str] = set()
    parts = module.split(".")
    candidates: list[Path] = [
        base_dir.joinpath(*parts).with_suffix(".py"),
        repo_root.joinpath(*parts).with_suffix(".py"),
        base_dir.joinpath(*parts) / "__init__.py",
        repo_root.joinpath(*parts) / "__init__.py",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            out.add(str(c.resolve().relative_to(repo_root)).replace("\\", "/"))
    return out


def _python_import_edges(repo_root: Path, file_rel: str, text: str) -> set[str]:
    edges: set[str] = set()
    file_path = repo_root / file_rel
    base_dir = file_path.parent
    import_re = re.compile(r"^\s*import\s+([a-zA-Z0-9_\.]+)", re.M)
    from_re = re.compile(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+", re.M)
    for m in import_re.finditer(text):
        edges |= _resolve_python_module(repo_root, base_dir, m.group(1))
    for m in from_re.finditer(text):
        edges |= _resolve_python_module(repo_root, base_dir, m.group(1))
    return edges


def _resolve_js_ts_spec(repo_root: Path, base_dir: Path, spec: str) -> set[str]:
    out: set[str] = set()
    abs_p = (base_dir / spec).resolve()
    try:
        rel = abs_p.relative_to(repo_root)
    except Exception:
        return out

    rel_str = str(rel).replace("\\", "/")
    p0 = repo_root / rel_str
    candidates: list[Path] = []
    if p0.suffix:
        candidates.append(p0)
    else:
        for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
            candidates.append(p0.with_suffix(ext))
        for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
            candidates.append(p0 / ("index" + ext))
    for c in candidates:
        if c.exists() and c.is_file():
            out.add(str(c.resolve().relative_to(repo_root)).replace("\\", "/"))
    return out


def _js_ts_import_edges(repo_root: Path, file_rel: str, text: str) -> set[str]:
    edges: set[str] = set()
    file_path = repo_root / file_rel
    base_dir = file_path.parent
    pat = re.compile(
        r"""(?x)
        (?:import|export)\s+[^;]*?\s+from\s+['"](?P<spec1>[^'"]+)['"]
        |
        (?:import)\s*['"](?P<spec2>[^'"]+)['"]
        |
        (?:require)\(\s*['"](?P<spec3>[^'"]+)['"]\s*\)
        """
    )
    for m in pat.finditer(text):
        spec = m.group("spec1") or m.group("spec2") or m.group("spec3") or ""
        if not spec.startswith("."):
            continue
        edges |= _resolve_js_ts_spec(repo_root, base_dir, spec)
    return edges


def classify_group(file_path: str) -> dict[str, str]:
    path = file_path.replace("\\", "/")
    if path.startswith("apps/admin-console/"):
        group_id = "admin_console"
    elif path.startswith(
        (
            "services/api-gateway/",
            "services/auth-service/",
            "services/workflow-service/",
            "services/mealbot-service/",
            "services/wecom-adapter/",
            "services/wecom-aibot-bridge/",
        )
    ):
        group_id = "campus_ops"
    elif path.startswith(
        (
            "services/rag-service/",
            "services/llm-gateway/",
            "services/knowledge-graph-service/",
            "services/source-ingestion-service/",
            "services/evaluation-service/",
            "services/ua-mcp-server/",
        )
    ):
        group_id = "knowledge_stack"
    elif path.startswith("services/crm-service/"):
        group_id = "crm_growth"
    elif path.startswith(
        (
            "services/permission-service/",
            "services/compliance-service/",
            "services/db-policy-service/",
        )
    ):
        group_id = "policy_security"
    elif path.startswith(("packages/", "configs/")) or "/fixtures/" in path:
        group_id = "shared_assets"
    elif path.startswith(("tests/", "tools/", "docs/")):
        group_id = "quality_ops"
    else:
        group_id = "other"

    group = next(item for item in GROUP_SPECS if item["id"] == group_id)
    return group


def build_file_graph(repo_root: Path) -> dict[str, Any]:
    # Keep this intentionally "code-focused" to stay renderable in a single-page HTML.
    include_exts = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".yaml",
        ".yml",
        ".toml",
        ".sql",
        ".proto",
    }
    exclude_dirs = {
        ".git",
        ".codegraph",
        ".venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        # large vendored deps / non-product code
        "external",
        # large runtime/data folders
        "data",
        "uploads",
    }
    files = _iter_repo_files(repo_root, include_exts=include_exts, exclude_dirs=exclude_dirs)
    file_set = set(files)
    group_stats: dict[str, dict[str, Any]] = {
        item["id"]: {**item, "count": 0, "protocols": set()} for item in GROUP_SPECS
    }

    nodes: list[dict[str, Any]] = []
    for f in files:
        p = repo_root / f
        group = classify_group(f)
        nodes.append(
            {
                "id": "file:" + f,
                "kind": "file",
                "name": p.name,
                "qualified_name": f,
                "file_path": f,
                "language": p.suffix.lower().lstrip("."),
                "group_id": group["id"],
                "group_title": group["title"],
                "group_description": group["description"],
                "group_color": group["color"],
            }
        )
        group_stats[group["id"]]["count"] += 1

    edges: list[dict[str, Any]] = []
    for f in files:
        p = repo_root / f
        ext = p.suffix.lower()
        if ext not in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
            continue
        text = _read_text(p)
        if not text:
            continue
        targets: set[str] = set()
        if ext == ".py":
            targets |= _python_import_edges(repo_root, f, text)
        else:
            targets |= _js_ts_import_edges(repo_root, f, text)
        for t in sorted(targets):
            if t not in file_set:
                continue
            edges.append({"source": "file:" + f, "target": "file:" + t, "kind": "imports", "weight": 1})

    file_protocols: dict[str, dict[str, Any]] = {}
    for f in files:
        hits = detect_protocols(repo_root / f)
        by_proto: dict[str, list[dict[str, Any]]] = {}
        for h in hits:
            by_proto.setdefault(h.protocol, []).append({"line": h.line, "snippet": h.snippet, "pattern": h.pattern})
        file_protocols[f] = {"protocols": sorted(by_proto.keys()), "evidence": by_proto}
    for n in nodes:
        fp = n["file_path"]
        n["protocols"] = file_protocols.get(fp, {}).get("protocols", [])
        for protocol in n["protocols"]:
            group_stats[n["group_id"]]["protocols"].add(protocol)

    groups = []
    for item in GROUP_SPECS:
        stat = group_stats[item["id"]]
        if stat["count"] == 0:
            continue
        groups.append(
            {
                "id": stat["id"],
                "title": stat["title"],
                "description": stat["description"],
                "color": stat["color"],
                "count": stat["count"],
                "protocols": sorted(stat["protocols"]),
            }
        )

    return {"nodes": nodes, "edges": edges, "file_protocols": file_protocols, "groups": groups}


def render_html(graph: dict[str, Any]) -> str:
    data_json = json.dumps(graph, ensure_ascii=False)
    safe_json = (
        data_json.replace("</", "<\\/")
        .replace("<!", "\\u003c!")
        .replace("<?", "\\u003c?")
    )
    generated = html.escape(graph.get("generated_at", ""))
    db_path = html.escape(graph.get("db_path", ""))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GaokaoAgent Code Graph</title>
  <style>
    :root {{
      --bg: #0b1220;
      --panel: #101a33;
      --panel2: #0f1730;
      --text: #e6edf7;
      --muted: #9fb0d0;
      --border: rgba(255,255,255,0.10);
      --accent: #7dd3fc;
      --warn: #fbbf24;
      --ok: #34d399;
    }}
    html, body {{ height: 100%; margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial; }}
    #app {{ display: grid; grid-template-columns: 360px minmax(0, 1fr) 420px; height: 100%; }}
    .panel {{ border-right: 1px solid var(--border); background: var(--panel); overflow: auto; }}
    .panel.right {{ border-right: none; border-left: 1px solid var(--border); background: var(--panel2); }}
    .header {{ padding: 14px 14px 10px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: linear-gradient(180deg, rgba(16,26,51,0.98), rgba(16,26,51,0.88)); backdrop-filter: blur(8px); }}
    .title {{ font-weight: 700; letter-spacing: 0.2px; }}
    .meta {{ font-size: 12px; color: var(--muted); margin-top: 6px; line-height: 1.35; }}
    .content {{ padding: 12px 14px 16px; }}
    input, select {{ width: 100%; padding: 10px 10px; border-radius: 10px; border: 1px solid var(--border); background: rgba(255,255,255,0.06); color: var(--text); outline: none; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
      .list {{ margin-top: 12px; }}
      .group-legend {{ margin-top: 12px; display: grid; gap: 8px; }}
      .group-card {{ border: 1px solid var(--border); border-radius: 12px; padding: 10px; background: rgba(255,255,255,0.035); }}
      .group-card .head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
      .group-card .title-line {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 650; }}
      .group-card .swatch {{ width: 10px; height: 10px; border-radius: 999px; flex: 0 0 auto; }}
      .group-card .count {{ font-size: 12px; color: var(--muted); }}
      .group-card .desc {{ margin-top: 6px; font-size: 12px; color: var(--muted); line-height: 1.4; }}
    .item {{ padding: 10px 10px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,0.04); margin-bottom: 10px; cursor: pointer; }}
    .item:hover {{ border-color: rgba(125,211,252,0.45); }}
    .item .name {{ font-weight: 650; font-size: 13px; word-break: break-word; }}
    .item .sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; word-break: break-word; }}
    .kbd {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; padding: 1px 6px; border-radius: 6px; background: rgba(255,255,255,0.08); border: 1px solid var(--border); color: var(--text); }}
    #graphWrap {{ position: relative; min-width: 0; min-height: 0; }}
    #graph {{ width: 100%; height: 100%; display: block; touch-action: none; }}
    #hint {{ position: absolute; left: 14px; bottom: 12px; font-size: 12px; color: var(--muted); background: rgba(0,0,0,0.35); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; max-width: 520px; }}
    .kv {{ display: grid; grid-template-columns: 120px 1fr; gap: 10px; padding: 6px 0; border-bottom: 1px dashed rgba(255,255,255,0.10); }}
    .k {{ color: var(--muted); font-size: 12px; }}
    .v {{ font-size: 12px; word-break: break-word; }}
    .proto {{ display: flex; flex-wrap: wrap; margin-top: 4px; }}
    .badge {{ display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 999px; border: 1px solid var(--border); margin: 4px 6px 0 0; font-size: 12px; }}
    .badge.ok {{ color: var(--ok); }}
    .badge.warn {{ color: var(--warn); }}
    .evidence {{ margin-top: 10px; }}
    .ev {{ padding: 8px 10px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,0.03); margin-bottom: 8px; }}
    .ev .line {{ color: var(--muted); font-size: 12px; }}
      .ev .snip {{ margin-top: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; white-space: pre-wrap; }}
      .zone-label {{ pointer-events: none; }}
  </style>
</head>
<body>
  <div id="app">
    <div class="panel">
      <div class="header">
        <div class="title">GaokaoAgent 代码图（全量文件图 + 协议标注）</div>
        <div class="meta">生成时间（UTC）：{generated}<br/>索引：<span class="kbd">{db_path}</span></div>
      </div>
      <div class="content">
        <input id="q" placeholder="搜索：文件名 / 路径 / qualified_name" />
        <div class="row">
          <select id="kind">
            <option value="">所有 kind</option>
          </select>
          <select id="edgeKind">
            <option value="">所有 edge</option>
          </select>
        </div>
        <div class="row">
          <select id="scope">
            <option value="files">只显示：文件（推荐）</option>
            <option value="all">显示：文件 + 符号（若数据源含符号）</option>
            <option value="symbols">只显示：符号</option>
          </select>
          <select id="protocol">
            <option value="">协议：全部</option>
          </select>
        </div>
        <div style="margin-top:10px; font-size:12px; color:var(--muted); line-height:1.35">
          操作：滚轮缩放；拖拽空白处平移；拖拽节点可定位。点击节点查看详情；Shift+点击高亮相邻边。<br/>
          协议标注为规则匹配推断（右侧显示证据行）。
        </div>
        <div class="group-legend" id="groupLegend"></div>
        <div class="list" id="list"></div>
      </div>
    </div>
    <div id="graphWrap">
      <svg id="graph"></svg>
      <div id="hint">
        <div><span class="kbd">滚轮</span>缩放　<span class="kbd">拖拽空白</span>平移　<span class="kbd">拖拽节点</span>固定位置</div>
      </div>
    </div>
    <div class="panel right">
      <div class="header">
        <div class="title">节点详情</div>
        <div class="meta">选择一个节点查看属性与通信协议证据</div>
      </div>
      <div class="content" id="detail"></div>
    </div>
  </div>

  <script id="graph-data" type="application/json">{safe_json}</script>
  <script>
    const RAW = JSON.parse(document.getElementById('graph-data').textContent);
    const ALL_NODES = RAW.nodes || [];
    const ALL_EDGES = RAW.edges || [];
    const FILE_PROTOCOLS = RAW.file_protocols || {{}};
    const GROUPS = RAW.groups || [];

    const NS = "http://www.w3.org/2000/svg";
    const svg = document.getElementById("graph");
    const wrap = document.getElementById("graphWrap");
    const width = () => Math.max(320, Math.round(wrap.getBoundingClientRect().width || wrap.clientWidth || (window.innerWidth - 780)));
    const height = () => Math.max(320, Math.round(wrap.getBoundingClientRect().height || wrap.clientHeight || window.innerHeight));

    function escapeHtml(s) {{
      return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
    }}
    function uniq(arr) {{
      return Array.from(new Set(arr)).sort((a,b)=>String(a).localeCompare(String(b)));
    }}
    function hashStr(s) {{
      s = String(s || "");
      let h = 2166136261;
      for (let i = 0; i < s.length; i++) {{
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }}
      return h | 0;
    }}
    const PALETTE = ["#7dd3fc","#34d399","#fbbf24","#f472b6","#a78bfa","#fb7185","#60a5fa","#f97316","#22c55e","#eab308","#38bdf8","#c084fc"];
    const EDGE_PALETTE = ["#64748b","#94a3b8","#7dd3fc","#34d399","#fbbf24","#a78bfa","#f472b6"];
    const color = (k) => PALETTE[Math.abs(hashStr(k)) % PALETTE.length];
    const edgeColor = (k) => EDGE_PALETTE[Math.abs(hashStr(k)) % EDGE_PALETTE.length];

    const kinds = uniq(ALL_NODES.map(n => n.kind));
    const edgeKinds = uniq(ALL_EDGES.map(e => e.kind));
    const protocols = uniq(Object.values(FILE_PROTOCOLS).flatMap(fp => (fp.protocols || [])));

    function renderGroupLegend() {{
      const el = document.getElementById('groupLegend');
      el.innerHTML = "";
      for (const group of GROUPS) {{
        const card = document.createElement('div');
        card.className = 'group-card';
        card.innerHTML = `
          <div class="head">
            <div class="title-line">
              <span class="swatch" style="background:${{group.color}}"></span>
              <span>${{escapeHtml(group.title)}}</span>
            </div>
            <span class="count">${{group.count}} files</span>
          </div>
          <div class="desc">${{escapeHtml(group.description)}}</div>
        `;
        el.appendChild(card);
      }}
    }}

    const kindSel = document.getElementById('kind');
    for (const k of kinds) {{
      const o = document.createElement('option'); o.value = k; o.textContent = k; kindSel.appendChild(o);
    }}
    const edgeSel = document.getElementById('edgeKind');
    for (const k of edgeKinds) {{
      const o = document.createElement('option'); o.value = k; o.textContent = k; edgeSel.appendChild(o);
    }}
    const protoSel = document.getElementById('protocol');
    for (const p of protocols) {{
      const o = document.createElement('option'); o.value = p; o.textContent = p; protoSel.appendChild(o);
    }}

    const zoomLayer = document.createElementNS(NS, "g");
    const linkLayer = document.createElementNS(NS, "g");
    const nodeLayer = document.createElementNS(NS, "g");
    linkLayer.setAttribute("stroke-opacity", "0.55");
    zoomLayer.appendChild(linkLayer);
    zoomLayer.appendChild(nodeLayer);
    svg.appendChild(zoomLayer);

    let view = {{ x: 0, y: 0, k: 1 }};
    function applyView() {{
      zoomLayer.setAttribute("transform", `translate(${{view.x}},${{view.y}}) scale(${{view.k}})`);
    }}
    applyView();

    // Pan/zoom background
    let panning = false;
    let panStart = {{ x: 0, y: 0, vx: 0, vy: 0 }};
    svg.addEventListener("pointerdown", (e) => {{
      if (e.target && e.target.tagName === "circle") return;
      panning = true;
      svg.setPointerCapture(e.pointerId);
      panStart = {{ x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }};
    }});
    svg.addEventListener("pointermove", (e) => {{
      if (!panning) return;
      view.x = panStart.vx + (e.clientX - panStart.x);
      view.y = panStart.vy + (e.clientY - panStart.y);
      applyView();
    }});
    svg.addEventListener("pointerup", (e) => {{
      panning = false;
      try {{ svg.releasePointerCapture(e.pointerId); }} catch {{}}
    }});
    svg.addEventListener("wheel", (e) => {{
      e.preventDefault();
      const delta = Math.sign(e.deltaY);
      const factor = delta > 0 ? 0.9 : 1.1;
      const rect = svg.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const k0 = view.k;
      const k1 = Math.min(4, Math.max(0.15, view.k * factor));
      view.x = mx - (mx - view.x) * (k1 / k0);
      view.y = my - (my - view.y) * (k1 / k0);
      view.k = k1;
      applyView();
    }}, {{ passive: false }});

    function clearLayer(layer) {{
      while (layer.firstChild) layer.removeChild(layer.firstChild);
    }}

    function filterGraph() {{
      const q = document.getElementById('q').value.trim().toLowerCase();
      const kind = kindSel.value;
      const edgeKind = edgeSel.value;
      const scope = document.getElementById('scope').value;
      const protocol = protoSel.value;

      let nodes = ALL_NODES;
      if (kind) nodes = nodes.filter(n => n.kind === kind);
      if (protocol) nodes = nodes.filter(n => (n.protocols || []).includes(protocol) || (FILE_PROTOCOLS[n.file_path]?.protocols || []).includes(protocol));
      if (q) {{
        nodes = nodes.filter(n =>
          String(n.name||"").toLowerCase().includes(q) ||
          String(n.qualified_name||"").toLowerCase().includes(q) ||
          String(n.file_path||"").toLowerCase().includes(q)
        );
      }}

      const idSet = new Set(nodes.map(n => n.id));
      let edges = ALL_EDGES.filter(e => idSet.has(e.source) && idSet.has(e.target));
      if (edgeKind) edges = edges.filter(e => e.kind === edgeKind);

      if (scope === "files") {{
        nodes = nodes.filter(n => n.kind === "file" || String(n.id||"").startsWith("file:"));
        const fset = new Set(nodes.map(n => n.id));
        edges = edges.filter(e => fset.has(e.source) && fset.has(e.target));
      }} else if (scope === "symbols") {{
        nodes = nodes.filter(n => n.kind !== "file" && !String(n.id||"").startsWith("file:"));
        const sset = new Set(nodes.map(n => n.id));
        edges = edges.filter(e => sset.has(e.source) && sset.has(e.target));
      }}
      return {{ nodes, edges }};
    }}

    function renderList(nodes) {{
      const list = document.getElementById('list');
      list.innerHTML = "";
      const top = nodes.slice(0, 60);
      for (const n of top) {{
        const div = document.createElement('div');
        div.className = 'item';
        div.onclick = () => selectNode(n.id);
        const name = (n.kind === "file" || String(n.id||"").startsWith("file:")) ? (n.file_path || n.qualified_name || n.name) : (n.qualified_name || n.name);
        const sub = `${{n.group_title || n.kind}} • ${{n.file_path || ""}}${{n.start_line ? (":" + n.start_line) : ""}}`;
        div.innerHTML = `<div class="name">${{escapeHtml(name)}}</div><div class="sub">${{escapeHtml(sub)}}</div>`;
        list.appendChild(div);
      }}
      if (nodes.length > top.length) {{
        const more = document.createElement('div');
        more.className = 'meta';
        more.style.marginTop = "10px";
        more.textContent = `已显示 60 / ${{nodes.length}} 个结果（进一步收窄筛选）`;
        list.appendChild(more);
      }}
    }}

    let current = {{ nodes: [], edges: [] }};
    let selectedId = null;

    function clearHighlight() {{
      for (const c of nodeLayer.querySelectorAll("circle")) c.setAttribute("opacity", "1.0");
      for (const l of linkLayer.querySelectorAll("line")) l.setAttribute("opacity", "0.55");
    }}

    function highlightNeighbors(id) {{
      const neighbors = new Set([id]);
      for (const e of current.edges) {{
        if (e.source === id) neighbors.add(e.target);
        if (e.target === id) neighbors.add(e.source);
      }}
      for (const c of nodeLayer.querySelectorAll("circle")) {{
        const nid = c.dataset.id;
        c.setAttribute("opacity", neighbors.has(nid) ? "1.0" : "0.15");
      }}
      for (const l of linkLayer.querySelectorAll("line")) {{
        const s = l.dataset.s, t = l.dataset.t;
        l.setAttribute("opacity", (s === id || t === id) ? "0.9" : "0.08");
      }}
    }}

    function selectNode(id, skipReset=false) {{
      if (!skipReset) clearHighlight();
      selectedId = id;
      const node = current.nodes.find(n => n.id === id) || null;
      const detail = document.getElementById('detail');
      if (!node) {{
        detail.innerHTML = `<div class="meta">当前筛选下找不到该节点：${{escapeHtml(id)}}</div>`;
        return;
      }}
      const isFile = node.kind === "file" || String(node.id).startsWith("file:");
      const filePath = isFile ? (node.file_path || node.qualified_name || "") : (node.file_path || "");
      const proto = isFile ? (FILE_PROTOCOLS[filePath]?.protocols || node.protocols || []) : (node.protocols || FILE_PROTOCOLS[filePath]?.protocols || []);
      const evidence = FILE_PROTOCOLS[filePath]?.evidence || {{}};

      const kv = (k,v) => `<div class="kv"><div class="k">${{escapeHtml(k)}}</div><div class="v">${{escapeHtml(v ?? "")}}</div></div>`;
      let htmlOut = "";
      htmlOut += kv("kind", node.kind);
      if (node.group_title) htmlOut += kv("agent_group", node.group_title);
      htmlOut += kv("name", node.name || "");
      htmlOut += kv("qualified_name", node.qualified_name || "");
      htmlOut += kv("file_path", filePath || "");
      if (node.start_line) htmlOut += kv("range", `${{node.start_line}}:${{node.start_column}} - ${{node.end_line}}:${{node.end_column}}`);
      if (node.signature) htmlOut += kv("signature", node.signature);
      if (node.visibility) htmlOut += kv("visibility", node.visibility);

      htmlOut += `<div style="margin-top:10px; font-weight:650">通信协议标注</div>`;
      htmlOut += `<div class="proto">` + (proto.length ? proto.map(p => `<span class="badge ok">${{escapeHtml(p)}}</span>`).join("") : `<span class="badge warn">未检测到</span>`) + `</div>`;

      const evBlocks = [];
      for (const [p, items] of Object.entries(evidence)) {{
        if (!proto.includes(p)) continue;
        for (const it of items.slice(0, 6)) {{
          evBlocks.push(`<div class="ev"><div class="line">${{escapeHtml(p)}} • L${{it.line}} • /${{escapeHtml(it.pattern)}}/</div><div class="snip">${{escapeHtml(it.snippet)}}</div></div>`);
        }}
      }}
      if (evBlocks.length) {{
        htmlOut += `<div class="evidence"><div class="meta" style="margin-bottom:8px;">证据（最多每协议 6 条）</div>${{evBlocks.join("")}}</div>`;
      }}
      detail.innerHTML = htmlOut;

      for (const c of nodeLayer.querySelectorAll("circle")) {{
        const nid = c.dataset.id;
        if (nid === id) {{
          c.setAttribute("stroke-width", "2.6");
          c.setAttribute("stroke", "rgba(251,191,36,0.95)");
        }} else {{
          c.setAttribute("stroke-width", "1.0");
          c.setAttribute("stroke", "rgba(0,0,0,0.65)");
        }}
      }}
    }}

    function buildZoneLayout(groups, w, h) {{
      const pad = 26;
      const gap = 18;
      const cols = w >= 1200 ? 3 : (w >= 820 ? 2 : 1);
      const rows = Math.max(1, Math.ceil(groups.length / cols));
      const zoneW = Math.max(220, (w - pad * 2 - gap * (cols - 1)) / cols);
      const zoneH = Math.max(180, (h - pad * 2 - gap * (rows - 1)) / rows);
      const zones = new Map();
      groups.forEach((group, index) => {{
        const col = index % cols;
        const row = Math.floor(index / cols);
        zones.set(group.id, {{
          ...group,
          x: pad + col * (zoneW + gap),
          y: pad + row * (zoneH + gap),
          width: zoneW,
          height: zoneH,
        }});
      }});
      return zones;
    }}

    function layoutNodesByZones(nodes, zones) {{
      const groups = new Map();
      for (const node of nodes) {{
        const groupId = node.group_id || 'other';
        if (!groups.has(groupId)) groups.set(groupId, []);
        groups.get(groupId).push(node);
      }}

      for (const [groupId, members] of groups.entries()) {{
        const zone = zones.get(groupId);
        if (!zone) continue;
        members.sort((a, b) => String(a.file_path || a.name).localeCompare(String(b.file_path || b.name)));
        const innerPadX = 18;
        const innerPadTop = 42;
        const innerPadBottom = 18;
        const usableW = Math.max(80, zone.width - innerPadX * 2);
        const usableH = Math.max(80, zone.height - innerPadTop - innerPadBottom);
        const cols = Math.max(1, Math.ceil(Math.sqrt(members.length)));
        const rows = Math.max(1, Math.ceil(members.length / cols));
        const cellW = usableW / cols;
        const cellH = usableH / rows;
        members.forEach((node, index) => {{
          const col = index % cols;
          const row = Math.floor(index / cols);
          node.x = zone.x + innerPadX + cellW * (col + 0.5);
          node.y = zone.y + innerPadTop + cellH * (row + 0.5);
          node.vx = 0;
          node.vy = 0;
          node.fx = null;
          node.fy = null;
        }});
      }}

      view.k = 1;
      view.x = 0;
      view.y = 0;
      applyView();
    }}

    function layoutAndDraw(nodes, edges) {{
      const w = width(), h = height();
      svg.setAttribute("viewBox", `0 0 ${{w}} ${{h}}`);
      view = {{ x: 0, y: 0, k: 1 }};
      applyView();

      clearLayer(linkLayer);
      clearLayer(nodeLayer);

      const activeGroupIds = uniq(nodes.map(n => n.group_id || 'other'));
      const activeGroups = GROUPS.filter(group => activeGroupIds.includes(group.id));
      const zones = buildZoneLayout(activeGroups, w, h);

      const nodeById = new Map(nodes.map(n => [n.id, n]));
      layoutNodesByZones(nodes, zones);

      for (const zone of zones.values()) {{
        const rect = document.createElementNS(NS, "rect");
        rect.setAttribute("x", String(zone.x));
        rect.setAttribute("y", String(zone.y));
        rect.setAttribute("width", String(zone.width));
        rect.setAttribute("height", String(zone.height));
        rect.setAttribute("rx", "18");
        rect.setAttribute("fill", `${{zone.color}}14`);
        rect.setAttribute("stroke", `${{zone.color}}99`);
        rect.setAttribute("stroke-width", "1.25");
        nodeLayer.appendChild(rect);

        const title = document.createElementNS(NS, "text");
        title.setAttribute("x", String(zone.x + 16));
        title.setAttribute("y", String(zone.y + 22));
        title.setAttribute("fill", zone.color);
        title.setAttribute("font-size", "13");
        title.setAttribute("font-weight", "700");
        title.setAttribute("class", "zone-label");
        title.textContent = `${{zone.title}} (${{zone.count}})`;
        nodeLayer.appendChild(title);

        const desc = document.createElementNS(NS, "text");
        desc.setAttribute("x", String(zone.x + 16));
        desc.setAttribute("y", String(zone.y + 38));
        desc.setAttribute("fill", "rgba(230,237,247,0.72)");
        desc.setAttribute("font-size", "10.5");
        desc.setAttribute("class", "zone-label");
        desc.textContent = zone.description;
        nodeLayer.appendChild(desc);
      }}

      const linkEls = [];
      for (const e of edges) {{
        const s = nodeById.get(e.source), t = nodeById.get(e.target);
        if (!s || !t) continue;
        e.__s = s; e.__t = t;
        const line = document.createElementNS(NS, "line");
        line.dataset.s = e.source;
        line.dataset.t = e.target;
        line.setAttribute("stroke", edgeColor(e.kind));
        const crossGroup = s.group_id !== t.group_id;
        const w0 = crossGroup ? 1.0 : 1.8;
        line.setAttribute("stroke-width", String(w0));
        line.setAttribute("stroke-opacity", crossGroup ? "0.28" : "0.55");
        linkLayer.appendChild(line);
        linkEls.push({{ e, line }});
      }}

      const nodeEls = [];
      for (const n of nodes) {{
        const c = document.createElementNS(NS, "circle");
        c.dataset.id = n.id;
        c.setAttribute("r", String((n.kind === "file" || String(n.id).startsWith("file:")) ? 4.6 : 4.0));
        c.setAttribute("fill", n.group_color || color(n.kind));
        c.setAttribute("stroke", "rgba(0,0,0,0.65)");
        c.setAttribute("stroke-width", "1.0");
        const title = document.createElementNS(NS, "title");
        title.textContent = `${{n.kind}}: ${{n.qualified_name || n.name}}`;
        c.appendChild(title);

        c.addEventListener("click", (event) => {{
          if (event.shiftKey) highlightNeighbors(n.id);
          else selectNode(n.id);
          event.stopPropagation();
        }});

        let dragging = false;
        c.addEventListener("pointerdown", (e) => {{
          dragging = true;
          c.setPointerCapture(e.pointerId);
          n.fx = n.x; n.fy = n.y;
        }});
        c.addEventListener("pointermove", (e) => {{
          if (!dragging) return;
          const rect = svg.getBoundingClientRect();
          const px = (e.clientX - rect.left - view.x) / view.k;
          const py = (e.clientY - rect.top - view.y) / view.k;
          n.fx = px; n.fy = py;
        }});
        c.addEventListener("pointerup", (e) => {{
          dragging = false;
          try {{ c.releasePointerCapture(e.pointerId); }} catch {{}}
          n.fx = null; n.fy = null;
        }});

        nodeLayer.appendChild(c);
        nodeEls.push({{ n, c }});
      }}

      function draw() {{
        for (const le of linkEls) {{
          const s = le.e.__s, t = le.e.__t;
          le.line.setAttribute("x1", String(s.x));
          le.line.setAttribute("y1", String(s.y));
          le.line.setAttribute("x2", String(t.x));
          le.line.setAttribute("y2", String(t.y));
        }}
        for (const ne of nodeEls) {{
          ne.c.setAttribute("cx", String(ne.n.x));
          ne.c.setAttribute("cy", String(ne.n.y));
        }}
      }}

      draw();
    }}

    function rerender() {{
      current = filterGraph();
      renderList(current.nodes);
      layoutAndDraw(current.nodes.map(n => ({{...n}})), current.edges.map(e => ({{...e}})));
      if (selectedId) selectNode(selectedId, true);
    }}

    for (const el of [document.getElementById('q'), kindSel, edgeSel, document.getElementById('scope'), protoSel]) {{
      el.addEventListener('input', () => rerender());
      el.addEventListener('change', () => rerender());
    }}
    window.addEventListener('resize', () => rerender());
    renderGroupLegend();
    rerender();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CodeGraph SQLite index into a self-contained HTML code graph.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to .codegraph/codegraph.db")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH, help="Output HTML path")
    parser.add_argument(
        "--include-all-files",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_INCLUDE_ALL_FILES,
        help="Also include a full-repo file-level import graph (recommended).",
    )
    args = parser.parse_args()

    db_path: Path = args.db
    out_path: Path = args.out

    if not db_path.exists():
        raise SystemExit(f"CodeGraph DB not found: {db_path}")

    graph = build_graph(db_path=db_path, repo_root=REPO_ROOT)
    if args.include_all_files:
        file_graph = build_file_graph(REPO_ROOT)
        # Prefer full-repo file graph for visualization; keep CodeGraph DB payload for reference.
        graph = {
            **graph,
            "nodes": file_graph["nodes"],
            "edges": file_graph["edges"],
            "file_protocols": file_graph["file_protocols"],
            "groups": file_graph["groups"],
            "codegraph_db": {
                "nodes": graph.get("nodes", []),
                "edges": graph.get("edges", []),
                "files": graph.get("files", {}),
            },
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(graph), encoding="utf-8")
    print(f"Wrote: {out_path}")

    # Also emit a tiny summary to stdout for CI usage if needed.
    print(f"Indexed files: {len(graph.get('files', {}))}")
    print(f"Nodes: {len(graph.get('nodes', []))}  Edges: {len(graph.get('edges', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
