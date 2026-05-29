# Docling Dependency Impact Report

Date: 2026-05-28
Branch: `chore/p1.5-evaluate-uv-sync-blast-radius`

## Dependency Origin

`docling` is a direct dependency of `source-ingestion-service` (one service out of 17).
It is declared as:

```toml
# services/source-ingestion-service/pyproject.toml
dependencies = ["docling"]
```

## Transitive Chain

```
source-ingestion-service
  └── docling v2.95.0
      └── docling-slim[standard] v2.95.0
          ├── docling-core v2.77.1
          │   ├── pandas v3.0.3 → numpy v2.4.6
          │   ├── pillow v12.2.0
          │   ├── pydantic v2.13.4
          │   └── ...
          └── docling-parse v3.x
              ├── torch v2.12.0 ← 390 MB
              ├── torchvision v0.27.0
              ├── transformers v5.9.0
              ├── scipy v1.15.0
              ├── opencv-python-headless (cv2)
              ├── sympy
              ├── scikit-image
              └── rapidocr-onnxruntime
```

## Size Impact

| Category | Size |
|---|---|
| Total `.venv` | 960 MB |
| docling family | ~47 MB (30 MB docling_parse + 17 MB rapidocr) |
| torch | 390 MB |
| opencv | 120 MB |
| scipy | 71 MB |
| transformers | 47 MB |
| **Total attributable to docling** | **~675 MB (70% of `.venv`)** |
| **Torch alone** | **390 MB (40% of `.venv`)** |

## Largest Single Files from docling subtree

| File | Size |
|---|---|
| `torch/lib/libtorch_cpu.dylib` | 241 MB |
| `torch/lib/libtorch_python.dylib` | 28 MB |
| `rapidocr/models/ch_PP-OCRv4_rec_infer.onnx` | 11 MB |

## Lockfile Representation

- `uv.lock` references `docling`: 39 times
- `uv.lock` references `torch`: 12 times
- `uv.lock` total lines: 2,997
- docling family contribution: ~600 lines (20% of lockfile)

## Risk Assessment

| Risk | Severity | Impact |
|---|---|---|
| Docker image bloat | High | Base image goes from ~200 MB to ~1.2 GB |
| CI cold install time | Medium | 38 s vs <10 s for pip baseline |
| CI warm install time | Low | 50 ms (cached) |
| Supply chain surface | High | docling adds 200+ transitive packages |
| SBOM size | High | 105 packages vs 5 for pip baseline |
| Vulnerability scanning | Medium | torch alone has known CVEs |
| ToB deployment | High | Customer build times and artifact sizes |

## Mitigation Options

| Option | Complexity | Impact |
|---|---|---|
| **Service-scoped CI jobs** | Low | Only `source-ingestion` jobs pay the docling cost |
| **Docker multi-stage build** | Medium | Base image stays light, docling in separate stage |
| **Dependency extras groups** | Medium | `source-ingestion[full]` vs `source-ingestion[core]` |
| **Separate build artifact** | High | Docling service built as independent Docker image |
| **Replace docling with lighter tool** | Very High | Requires reimplementing document parsing |

## Recommendation

**Service-scoped CI + Docker multi-stage is the preferred approach:**

1. Keep `uv.lock` as a single source of truth (already committed in P1).
2. CI for `source-ingestion-service` uses `uv sync --package metacampus-source-ingestion-service`.
3. All other CI jobs use `uv sync --package <name>` (or skip for stdlib services).
4. Docker: base image built without source-ingestion; docling added in a separate layer.
5. Do NOT switch to root `uv sync --all-packages` in CI or Docker.
