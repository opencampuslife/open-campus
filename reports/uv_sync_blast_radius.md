# uv sync Blast Radius Report

Date: 2026-05-28
Branch: `chore/p1.5-evaluate-uv-sync-blast-radius`
Environment: macOS (aarch64), Python 3.11

## Executive Summary

**Root `uv sync --all-packages` creates a 960 MB `.venv`** — unacceptable for CI and Docker builds.
Service-scoped sync is essential before adopting `uv sync` anywhere.

## Key Metrics

| Metric | Value |
|---|---|
| Cold sync time | 38.2 s |
| Warm sync time | 50 ms |
| `.venv` total size | 960 MB |
| Total files | 27,943 |
| Packages installed | 105 |
| Packages resolved (lockfile) | 145 |
| Service causing >90% of bloat | `source-ingestion-service` (docling) |

## `.venv` Breakdown — Top Heaviest Packages

| Package | Size | % of total | Origin |
|---|---|---|---|
| `torch` | 390 MB | 40.6% | docling → transformers |
| `opencv (cv2)` | 120 MB | 12.5% | docling_parse |
| `scipy` | 71 MB | 7.4% | docling_parse |
| `transformers` | 47 MB | 4.9% | docling_parse |
| `pandas` | 40 MB | 4.2% | docling-core |
| `docling_parse` | 30 MB | 3.1% | docling |
| `sympy` | 29 MB | 3.0% | docling_parse |
| `numpy` | 22 MB | 2.3% | transitive |
| `lxml` | 19 MB | 2.0% | docling-core |
| `rapidocr` | 17 MB | 1.8% | docling |
| Other (95 packages) | 183 MB | 19.1% |

**Top 5 packages account for 69% of total `.venv` size** (648 MB / 960 MB).

## Largest Single Files

| File | Size |
|---|---|
| `torch/lib/libtorch_cpu.dylib` | 241 MB |
| `cv2/cv2.abi3.so` | 34 MB |
| `torch/lib/libtorch_python.dylib` | 28 MB |
| `rapidocr/models/ch_PP-OCRv4_rec_infer.onnx` | 11 MB |

## Service Contamination Analysis

When using root `uv sync --all-packages`:

| Service | Deps needed | Packages installed | Waste |
|---|---|---|---|
| `auth-service` | 0 | 105 | 105 unwanted packages |
| `crm-service` | 0 | 105 | 105 unwanted packages |
| `rag-service` | 0 | 105 | 105 unwanted packages |
| `agent-orchestrator` | 0 | 105 | 105 unwanted packages |
| `evaluation-service` | 0 | 105 | 105 unwanted packages |
| ... (11 stdlib-only services) | 0 | 105 | 105 each |
| `wecom-adapter` | 1 | 105 | 104 unwanted |
| `llm-gateway` | 1 | 105 | 104 unwanted |
| `api-gateway` | 2 | 105 | 103 unwanted |
| `mealbot-service` | 3 | 105 | 102 unwanted |
| `knowledge-service` | 4 | 105 | 101 unwanted |
| `source-ingestion-service` | 1 | 105 | 0 (needs all) |

**11 of 17 Python services need zero third-party packages** but would still get 105 installed.

## Scenario Comparison

| Scenario | CI time | Size | Verdict |
|---|---|---|---|
| **Current** (pip install 5 tools) | <10 s | <5 MB | ✅ Baseline |
| **Root `uv sync --all-packages`** | 38 s | 960 MB | ❌ Unacceptable |
| **Service-scoped (stdlib service)** | <1 s | 0 MB | ✅ Same as pip |
| **Service-scoped (source-ingestion)** | 38 s | 960 MB | ⚠️ High cost, unavoidable |

## Key Findings

1. **Root `uv sync --all-packages` is not viable** — 960 MB `.venv`, 38 s cold install.
2. **`source-ingestion-service` (docling) causes 96% of bloat** — torch alone is 390 MB.
3. **Service contamination is severe** — a pure-stdlib service gets 105 packages for no benefit.
4. **docker image delta**: pip-only = ~200 MB, uv-sync-all = ~1.2 GB (6× increase).
5. **CI runtime delta**: pip = <10 s, uv-sync = 38 s (3.8× increase for no gain on most jobs).

## Recommendations

1. **DO NOT** switch CI to root `uv sync --all-packages`.
2. **Prefer** `uv sync --package <name>` for individual CI jobs.
3. **For stdlib-only services**: use `uv sync --no-install-project` or skip entirely.
4. **For docling-heavy jobs**: isolate in a separate Docker stage or CI runner.
5. **Consider** extras/dependency groups: `source-ingestion[document-ai]` vs `source-ingestion[minimal]`.
6. **Plan** Docker multi-stage builds to keep docling out of the base image.
