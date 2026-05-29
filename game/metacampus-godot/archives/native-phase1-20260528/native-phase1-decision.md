# Native Phase 1 Decision Record

> 归档于：2026-05-28
> 决策人：Kevin（项目负责人）
> 执行：Mavis Agent Team（4 agents）

## Decision

**Stop after GDExtension PoC and performance baseline.**
Do not proceed with NativePathfinder in Phase 2.

## Evidence

- Godot 4.6 project structure verified (12 GDScript modules, 2665 LOC).
- GDExtension PoC builds and loads successfully via godot-cpp / SCons / .gdextension.
- macOS arm64 .dylib (201 KB) produced, Godot headless load + ClassDB invoke verified.
- NPC gradient benchmark completed at 10/50/100/300 NPC.
- **Pathfinding/frame P95 at 300 NPC: 3.3μs.**
- API mock P95 latency: 15.66ms (~4,500× the pathfinding cost).
- Smoke full run: 10.8s (68/68 pass).
- JSON config loads: all sub-300μs.

## Rationale

Pathfinding is not a material bottleneck at current scale. The P95 frame processing cost grows only 1.3× (2.6μs → 3.3μs) from 10 to 300 NPC. A C++ native rewrite would not produce any user-facing improvement. The real bottleneck is API latency (15ms P95), which is ~4,500× larger.

Continuing NativePathfinder would be migrating for the sake of the plan, not based on data.

## Agent Team Performance

| Agent | Model | Task | Outcome |
|-------|-------|------|---------|
| meta-explorer | deepseek-v4-flash | Structure scan | ✅ |
| perf-benchmarker | deepseek-v4-flash | Performance baseline | ✅ Key finding |
| gd-extension-dev | deepseek-v4-pro | GDExtension PoC | ✅ Proof of capability |
| pathfinder-coder | deepseek-v4-pro | NativePathfinder | ❌ Cancelled (data-driven) |

## Follow-up Priority (as of 2026-05-28)

| Pri | Work Item | Rationale |
|-----|-----------|-----------|
| P0 | Archive Phase 1 report bundle | Freeze evidence chain |
| P1 | Break down API mock/live/off/fallback latency | Current 15ms dominant, far larger than pathfinding |
| P1 | Request queue, timeout, cancel, caching | Directly improves interactive response |
| P2 | NPC behavior logic stress test (300+ NPC) | Identify real hotspots |
| P2 | Smoke test optimization | 10.8s is a reasonable CI UX target |
| P3 | Keep GDExtension template for future use | Ready when a real performance wall emerges |
| P4 | NativePathfinder | Paused, not deleted or designed |
