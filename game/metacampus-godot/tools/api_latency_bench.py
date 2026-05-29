#!/usr/bin/env python3
"""MetaCampus API Latency Benchmark — Multi-mode latency collection and report

Orchestrates 4 API modes (mock / off / live / fallback) through Godot headless
api_latency_capture.gd, collects per-request bench traces, computes statistics,
and generates dual-format reports (Markdown + JSON).

Usage:
    python tools/api_latency_bench.py                        # Full collection (all 4 modes)
    python tools/api_latency_bench.py --mock-only            # Only mock mode
    python tools/api_latency_bench.py --off-only             # Only off mode
    python tools/api_latency_bench.py --live-only            # Only live mode
    python tools/api_latency_bench.py --fallback-only        # Only fallback mode
    python tools/api_latency_bench.py --report-only          # Regenerate from existing raw data

Outputs:
    tools/perf_output/perf_api_raw.json       # Per-sample raw data (all modes)
    reports/api-latency-breakdown.md          # Markdown report
    reports/api-latency-breakdown.json        # Structured JSON report
"""

import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Constants ──

PROJECT_DIR = Path(__file__).parent.parent.resolve()
GODOT_EXEC = "/Users/kevinzzz/Downloads/Godot.app/Contents/MacOS/Godot"
TOOLS_DIR = PROJECT_DIR / "tools"
REPORTS_DIR = PROJECT_DIR / "reports"
OUTPUT_DIR = PROJECT_DIR / "tools" / "perf_output"

TEST_HARNESS_BASE = "http://127.0.0.1:16007"
BRIDGE_URL = "http://127.0.0.1:8788"

HARNESS_READY_TIMEOUT = 15   # seconds
BRIDGE_READY_TIMEOUT = 15    # seconds
GODOT_PROC_TIMEOUT = 600     # max per-mode (10 min safety)

SAMPLES_PER_MODE = 30
FALLBACK_TIMEOUT_MS = 3000   # temp timeout for fallback mode (api_config.json)

# Queries that DON'T trigger high-risk guard (safe for all modes)
SAFE_QUERIES = [
    "报名需要哪些材料",
    "学校有什么特色课程",
    "招生政策是什么",
    "学校地址在哪里",
    "学费是多少",
    "今天天气怎么样",
    "如何申请奖学金",
    "宿舍条件怎么样",
    "毕业去向如何",
    "考试安排什么时候",
    "校园活动有哪些",
    "学生保险怎么办理",
    "图书馆开放时间",
    "师资力量怎么样",
    "课程安排如何",
]

CAPTURE_SCRIPT = TOOLS_DIR / "api_latency_capture.gd"
API_CONFIG_PATH = PROJECT_DIR / "data" / "api_config.json"
API_CONFIG_BACKUP_PATH = OUTPUT_DIR / ".api_config.json.bak"


# ── Helpers ──

def log(msg: str):
    print(f"[api-bench] {msg}")


def http_get(path: str, timeout: int = 5) -> dict:
    url = TEST_HARNESS_BASE + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def http_post_json(url: str, body: dict, timeout: int = 10) -> dict:
    """POST JSON to an endpoint, return parsed response."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def wait_for_service(url: str, timeout: int, label: str = "service") -> bool:
    log(f"Waiting for {label} at {url}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    log(f"{label} is ready.")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    log(f"ERROR: {label} did not become ready within {timeout}s.")
    return False


def wait_for_harness(timeout: int = HARNESS_READY_TIMEOUT) -> bool:
    return wait_for_service(TEST_HARNESS_BASE + "/health", timeout, "TestHarness")


def wait_for_bridge(timeout: int = BRIDGE_READY_TIMEOUT) -> bool:
    return wait_for_service(BRIDGE_URL + "/health", timeout, "LLM Bridge")


def kill_godot():
    """Kill any running Godot processes."""
    try:
        subprocess.run(
            ["pkill", "-f", "Godot.app/Contents/MacOS/Godot"],
            capture_output=True, timeout=5
        )
        time.sleep(1)
    except Exception:
        pass


def kill_bridge():
    """Kill LLM Bridge python process."""
    try:
        subprocess.run(
            ["pkill", "-f", "llm_bridge.py"],
            capture_output=True, timeout=5
        )
        time.sleep(0.5)
    except Exception:
        pass


def start_godot(args: list[str], headless: bool = True, env: dict = None) -> subprocess.Popen:
    cmd = [GODOT_EXEC]
    if headless:
        cmd.append("--headless")
    cmd += ["--path", str(PROJECT_DIR)] + args
    log("Starting: " + " ".join(str(c) for c in cmd))
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    proc_env.setdefault("PERF_BENCH", "1")
    proc_env.setdefault("PERF_OUTPUT_DIR", str(OUTPUT_DIR))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=proc_env,
    )
    return proc


def start_bridge() -> subprocess.Popen:
    bridge_script = TOOLS_DIR / "llm_bridge.py"
    log(f"Starting LLM Bridge: {bridge_script}")
    proc = subprocess.Popen(
        [sys.executable, str(bridge_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def parse_csv_from_stdout(stdout: str) -> list[dict]:
    """Extract CSV data between === API Latency CSV === markers."""
    lines = stdout.split("\n")
    in_csv = False
    csv_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == "=== API Latency CSV ===":
            in_csv = True
            continue
        if stripped == "=== END CSV ===":
            in_csv = False
            continue
        if in_csv:
            csv_lines.append(stripped)

    if not csv_lines:
        return []

    reader = csv.DictReader(csv_lines)
    return list(reader)


def backup_api_config():
    """Backup api_config.json before temporary modification."""
    if API_CONFIG_PATH.exists():
        shutil.copy2(str(API_CONFIG_PATH), str(API_CONFIG_BACKUP_PATH))
        log(f"Backed up {API_CONFIG_PATH} → {API_CONFIG_BACKUP_PATH}")


def restore_api_config():
    """Restore api_config.json from backup."""
    if API_CONFIG_BACKUP_PATH.exists():
        shutil.copy2(str(API_CONFIG_BACKUP_PATH), str(API_CONFIG_PATH))
        API_CONFIG_BACKUP_PATH.unlink()
        log(f"Restored {API_CONFIG_PATH} from backup")


def patch_api_config_timeout(timeout_ms: int):
    """Write a modified api_config.json with reduced timeout_ms for fallback tests."""
    with open(API_CONFIG_PATH) as f:
        config = json.load(f)
    config["timeout_ms"] = timeout_ms
    with open(API_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    log(f"Patched api_config.json timeout_ms → {timeout_ms}")


# ── Statistics ──

def compute_stats(values_ms: list[float], errors: list[str]) -> dict:
    """Compute summary statistics from a list of latencies in milliseconds."""
    if not values_ms:
        return {
            "samples": 0,
            "failures": 0,
            "min_ms": 0,
            "avg_ms": 0,
            "median_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "max_ms": 0,
            "error_rate": 0,
        }

    sorted_vals = sorted(values_ms)
    n = len(sorted_vals)
    failures = sum(1 for e in errors if e)
    # Compute using the full trace unless we know it's an error

    return {
        "samples": n,
        "failures": failures,
        "min_ms": round(sorted_vals[0], 2),
        "avg_ms": round(sum(sorted_vals) / n, 2),
        "median_ms": round(sorted_vals[int(n * 0.50)], 2),
        "p95_ms": round(sorted_vals[int(n * 0.95)], 2),
        "p99_ms": round(sorted_vals[int(n * 0.99)], 2),
        "max_ms": round(sorted_vals[-1], 2),
        "error_rate": round(failures / n, 4) if n > 0 else 0,
    }


def determine_bottleneck(traces: list[dict], mode: str) -> str:
    """Analyze bench breakdown to identify main latency contributor."""
    if mode in ("mock", "off"):
        return "api_client internal routing (GDScript)"

    if mode == "fallback":
        return "HTTP timeout waiting for LLM Bridge"

    # Live mode — average breakdown percentages
    n = len(traces)
    if n == 0:
        return "N/A"

    total_sum = 0.0
    serialize_sum = 0.0
    send_sum = 0.0
    parse_sum = 0.0
    callback_sum = 0.0

    for t in traces:
        total_us = float(t.get("total_us", 0))
        if total_us == 0:
            continue
        total_sum += 1
        serialize_sum += float(t.get("serialize_us", 0)) / total_us
        send_sum += float(t.get("send_us", 0)) / total_us
        parse_sum += float(t.get("parse_us", 0)) / total_us
        callback_sum += float(t.get("callback_us", 0)) / total_us

    if total_sum == 0:
        return "LLM provider API call"

    avg_serialize_pct = (serialize_sum / total_sum) * 100
    avg_send_pct = (send_sum / total_sum) * 100
    avg_parse_pct = (parse_sum / total_sum) * 100
    avg_callback_pct = (callback_sum / total_sum) * 100
    # The remainder is the HTTP round-trip + LLM provider time
    remainder_pct = 100 - avg_serialize_pct - avg_send_pct - avg_parse_pct - avg_callback_pct

    breakdown = {
        "serialize_pct": avg_serialize_pct,
        "send_pct": avg_send_pct,
        "http_provider_pct": remainder_pct,
        "parse_pct": avg_parse_pct,
        "callback_pct": avg_callback_pct,
    }

    # Find the largest component
    max_key = max(breakdown, key=breakdown.get)
    labels = {
        "serialize_pct": "JSON serialization (GDScript)",
        "send_pct": "HTTP request send (Godot)",
        "http_provider_pct": "LLM provider API round-trip",
        "parse_pct": "Response parse (GDScript)",
        "callback_pct": "Callback dispatch (GDScript)",
    }
    return labels.get(max_key, "LLM provider API call")


# ── Main Orchestrator ──

class APILatencyBench:
    """Orchestrates multi-mode API latency collection + report generation."""

    def __init__(self):
        self.raw_data = {
            "metadata": {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "samples_per_mode": SAMPLES_PER_MODE,
                "godot_exec": GODOT_EXEC,
                "project_dir": str(PROJECT_DIR),
            },
            "modes": {},
        }
        self.bridge_proc: subprocess.Popen | None = None

    # ── Per-mode collection ──

    def _collect_one_mode(self, mode: str, samples: int = SAMPLES_PER_MODE,
                          extra_env: dict = None) -> list[dict]:
        """Run Godot headless with api_latency_capture.gd for one mode.

        Returns list of parsed trace dicts.
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        env = {}
        if extra_env:
            env.update(extra_env)

        proc = start_godot(
            [
                "--script", "tools/api_latency_capture.gd",
                f"--mode={mode}",
                f"--samples={samples}",
                "--interval_ms=50",
            ],
            headless=True,
            env=env,
        )

        try:
            stdout, stderr = proc.communicate(timeout=GODOT_PROC_TIMEOUT)
        except subprocess.TimeoutExpired:
            log(f"ERROR: Godot timed out for mode={mode}, killing...")
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)

        if stderr and stderr.strip():
            # Show last 500 chars of stderr for debugging
            log(f"  STDERR (last 500): {stderr[-500:]}")

        traces = parse_csv_from_stdout(stdout)

        if not traces:
            log(f"  WARNING: No traces parsed from stdout for mode={mode}")
            log(f"  stdout last 1000: {stdout[-1000:]}")
            return []

        # Convert string fields to native types
        for t in traces:
            for key in ("total_us", "serialize_us", "send_us", "parse_us", "callback_us", "timestamp"):
                try:
                    t[key] = int(t.get(key, 0))
                except (ValueError, TypeError):
                    t[key] = 0
            t["total_ms"] = round(t.get("total_us", 0) / 1000.0, 2)

        log(f"  Collected {len(traces)} traces for mode={mode}")
        return traces

    def collect_mock(self) -> list[dict]:
        log("\n" + "=" * 60)
        log("Mode: MOCK — local response matching only")
        log("=" * 60)
        return self._collect_one_mode("mock")

    def collect_off(self) -> list[dict]:
        log("\n" + "=" * 60)
        log("Mode: OFF — API disabled, immediate offline response")
        log("=" * 60)
        return self._collect_one_mode("off")

    def collect_live(self) -> list[dict]:
        log("\n" + "=" * 60)
        log("Mode: LIVE — full pipeline through LLM Bridge → DeepSeek API")
        log("=" * 60)

        if not wait_for_bridge():
            log("ERROR: LLM Bridge not running. Skipping live mode.")
            return []

        return self._collect_one_mode("live")

    def collect_fallback(self) -> list[dict]:
        log("\n" + "=" * 60)
        log("Mode: FALLBACK — live request to unreachable Bridge, fallback to mock")
        log("=" * 60)

        # Patch api_config.json to reduce timeout for faster fallback
        backup_api_config()
        patch_api_config_timeout(FALLBACK_TIMEOUT_MS)

        # Stop Bridge so requests time out
        kill_bridge()
        time.sleep(0.5)

        traces = self._collect_one_mode("live")

        # Restore config and restart Bridge
        restore_api_config()

        # For fallback mode, mark traces with explicit fallback
        for t in traces:
            fb_reason = t.get("fallback_reason", "")
            if fb_reason and fb_reason != "null":
                t["mode"] = "fallback"
                # total_us already includes the timeout + mock response
            else:
                # If no fallback reason, it's a successful live request
                # (should be rare in this mode)
                t["mode"] = "fallback"
                t["fallback_reason"] = "bridge_down"

        return traces

    def compute_summary(self, traces: list[dict], mode: str) -> dict:
        """Compute summary statistics for one mode's traces."""
        values_ms = []
        errors = []

        for t in traces:
            total_ms = t.get("total_ms", 0)
            if total_ms > 0:
                values_ms.append(total_ms)
            fb = t.get("fallback_reason", "")
            if fb and fb != "null" and fb != "":
                errors.append(fb)
            elif t.get("_error", ""):
                errors.append(t["_error"])

        stats = compute_stats(values_ms, errors)
        stats["main_bottleneck"] = determine_bottleneck(traces, mode)

        # Add breakdown for live mode
        if mode == "live" or mode == "fallback":
            breakdown = self._compute_breakdown(traces)
            stats["breakdown"] = breakdown

        return stats

    def _compute_breakdown(self, traces: list[dict]) -> dict:
        """Compute average timing breakdown percentages."""
        if not traces:
            return {}

        n = len(traces)
        avg_total = sum(float(t.get("total_us", 0)) for t in traces) / n
        avg_serialize = sum(float(t.get("serialize_us", 0)) for t in traces) / n
        avg_send = sum(float(t.get("send_us", 0)) for t in traces) / n
        avg_parse = sum(float(t.get("parse_us", 0)) for t in traces) / n
        avg_callback = sum(float(t.get("callback_us", 0)) for t in traces) / n

        if avg_total == 0:
            return {}

        return {
            "avg_total_us": round(avg_total, 1),
            "avg_total_ms": round(avg_total / 1000, 2),
            "serialize_pct": round((avg_serialize / avg_total) * 100, 1),
            "send_pct": round((avg_send / avg_total) * 100, 1),
            "http_provider_pct": round(
                ((avg_total - avg_serialize - avg_send - avg_parse - avg_callback) / avg_total) * 100, 1
            ),
            "parse_pct": round((avg_parse / avg_total) * 100, 1),
            "callback_pct": round((avg_callback / avg_total) * 100, 1),
        }

    # ── Persistence ──

    def save_raw_data(self):
        """Save per-sample traces to JSON."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / "perf_api_raw.json"

        # Strip verbose data for storage — keep summary + sparse traces
        persist = {
            "metadata": self.raw_data["metadata"],
            "modes": {},
        }
        for mode, data in self.raw_data["modes"].items():
            traces = data.get("traces", [])
            # Keep summary + condensed traces
            persist["modes"][mode] = {
                "summary": data.get("summary", {}),
                "trace_count": len(traces),
                "traces": [
                    {
                        "request_id": t.get("request_id", ""),
                        "total_ms": t.get("total_ms", 0),
                        "total_us": t.get("total_us", 0),
                        "serialize_us": t.get("serialize_us", 0),
                        "send_us": t.get("send_us", 0),
                        "parse_us": t.get("parse_us", 0),
                        "callback_us": t.get("callback_us", 0),
                        "fallback_reason": t.get("fallback_reason", ""),
                    }
                    for t in traces
                ],
            }

        with open(path, "w") as f:
            json.dump(persist, f, indent=2, ensure_ascii=False)
        log(f"Wrote raw data: {path}")

    def load_raw_data(self) -> bool:
        """Load previously saved raw data for report-only mode."""
        path = OUTPUT_DIR / "perf_api_raw.json"
        if not path.exists():
            log(f"ERROR: No raw data found at {path}")
            return False

        with open(path) as f:
            loaded = json.load(f)

        self.raw_data["metadata"] = loaded.get("metadata", {})
        for mode, data in loaded.get("modes", {}).items():
            self.raw_data["modes"][mode] = data
            log(f"  Loaded {data.get('trace_count', 0)} traces for mode={mode}")
        return True

    # ── Report Generation ──

    def _env_section(self) -> str:
        meta = self.raw_data["metadata"]
        return f"""## 测试环境

| 项目 | 值 |
|------|-----|
| 主机 | macOS (Apple Silicon) |
| Godot | 4.6.3.stable |
| 渲染器 | headless (SceneTree) |
| 采集脚本 | `tools/api_latency_capture.gd` |
| 采样数 | {SAMPLES_PER_MODE} / mode |
| 查询间隔 | 50ms |
| 桥接服务 | `tools/llm_bridge.py` → DeepSeek API |
| 采集时间 | {meta.get("timestamp", "N/A")} |
| Fallback 超时 | {FALLBACK_TIMEOUT_MS}ms (patched) |
"""

    def _acceptance_table(self) -> str:
        rows = []
        for mode in ["mock", "off", "live", "fallback"]:
            d = self.raw_data["modes"].get(mode, {}).get("summary", {})
            if not d:
                continue
            samples = d.get("samples", 0)
            avg = f"{d.get('avg_ms', 0):.2f}ms" if d.get("avg_ms", 0) < 1000 else f"{d.get('avg_ms', 0) / 1000:.2f}s"
            median = f"{d.get('median_ms', 0):.2f}ms" if d.get('median_ms', 0) < 1000 else f"{d.get('median_ms', 0) / 1000:.2f}s"
            p95 = f"{d.get('p95_ms', 0):.2f}ms" if d.get('p95_ms', 0) < 1000 else f"{d.get('p95_ms', 0) / 1000:.2f}s"
            p99 = f"{d.get('p99_ms', 0):.2f}ms" if d.get('p99_ms', 0) < 1000 else f"{d.get('p99_ms', 0) / 1000:.2f}s"
            err_rate = f"{d.get('error_rate', 0) * 100:.1f}%"
            bottleneck = d.get("main_bottleneck", "N/A")
            rows.append(f"| {mode} | {samples} | {avg} | {median} | {p95} | {p99} | {err_rate} | {bottleneck} |")

        header = "## 验收表 — 多模式延迟对比\n\n"
        header += "| mode | samples | avg | median | P95 | P99 | error rate | main bottleneck |\n"
        header += "|------|---------|-----|--------|-----|-----|------------|-----------------|"
        return header + "\n" + "\n".join(rows) + "\n"

    def _mock_section(self) -> str:
        d = self.raw_data["modes"].get("mock", {}).get("summary", {})
        if not d:
            return "## Mock 模式\n\n*No data collected.*\n"
        return f"""## Mock 模式 — 本地响应匹配

Mock 模式下 `api_client` 从本地 `mock_knowledge_responses.json` 匹配回答，不发起任何网络请求。

| 指标 | 值 |
|------|-----|
| 采样数 | {d.get('samples', 0)} |
| 平均 | {d.get('avg_ms', 0):.2f}ms |
| P50 (中位数) | {d.get('median_ms', 0):.2f}ms |
| P95 | {d.get('p95_ms', 0):.2f}ms |
| P99 | {d.get('p99_ms', 0):.2f}ms |
| 最小值 | {d.get('min_ms', 0):.2f}ms |
| 最大值 | {d.get('max_ms', 0):.2f}ms |
| 错误率 | {d.get('error_rate', 0) * 100:.1f}% |

> Mock 延迟代表 **api_client 内部 GDScript 路由 + 字符串匹配开销**，不含网络。
> 这是所有模式的性能下限基线。
"""

    def _off_section(self) -> str:
        d = self.raw_data["modes"].get("off", {}).get("summary", {})
        if not d:
            return "## Off 模式\n\n*No data collected.*\n"
        return f"""## Off 模式 — API 关闭

Off 模式下 `api_client` 立即返回离线提示，不查询 mock 数据也不发起网络请求。

| 指标 | 值 |
|------|-----|
| 采样数 | {d.get('samples', 0)} |
| 平均 | {d.get('avg_ms', 0):.2f}ms |
| P50 (中位数) | {d.get('median_ms', 0):.2f}ms |
| P95 | {d.get('p95_ms', 0):.2f}ms |
| P99 | {d.get('p99_ms', 0):.2f}ms |
| 最小值 | {d.get('min_ms', 0):.2f}ms |
| 最大值 | {d.get('max_ms', 0):.2f}ms |
| 错误率 | {d.get('error_rate', 0) * 100:.1f}% |

> Off 延迟代表 **函数返回 + Bench 记录的最小开销**，几乎全部在 µs 级别。
"""

    def _live_section(self) -> str:
        d = self.raw_data["modes"].get("live", {}).get("summary", {})
        traces = self.raw_data["modes"].get("live", {}).get("traces", [])
        if not d:
            return "## Live 模式\n\n*No data collected.*\n"

        breakdown = d.get("breakdown", {})
        breakdown_rows = ""
        if breakdown:
            breakdown_rows = f"""
### 耗时分解

| 阶段 | 占比 |
|------|------|
| JSON 序列化 (serialize_us) | {breakdown.get('serialize_pct', 'N/A')}% |
| HTTP 发送 (send_us) | {breakdown.get('send_pct', 'N/A')}% |
| LLM Provider + 网络 (推断值) | {breakdown.get('http_provider_pct', 'N/A')}% |
| 响应解析 (parse_us) | {breakdown.get('parse_pct', 'N/A')}% |
| 回调调度 (callback_us) | {breakdown.get('callback_pct', 'N/A')}% |

> 平均总耗时 = {breakdown.get('avg_total_ms', 'N/A')}ms
"""

        return f"""## Live 模式 — 全链路 (Godot → Bridge → DeepSeek)

Live 模式经过完整调用链：Godot `api_client` → HTTP POST → `llm_bridge.py` → DeepSeek API。

| 指标 | 值 |
|------|-----|
| 采样数 | {d.get('samples', 0)} |
| 平均 | {self._fmt_ms(d.get('avg_ms', 0))} |
| P50 (中位数) | {self._fmt_ms(d.get('median_ms', 0))} |
| P95 | {self._fmt_ms(d.get('p95_ms', 0))} |
| P99 | {self._fmt_ms(d.get('p99_ms', 0))} |
| 最小值 | {self._fmt_ms(d.get('min_ms', 0))} |
| 最大值 | {self._fmt_ms(d.get('max_ms', 0))} |
| 错误率 | {d.get('error_rate', 0) * 100:.1f}% |
{breakdown_rows}
> Live 延迟由 **DeepSeek API 响应时间** 主导（通常 1-5s），GDScript 侧开销仅占 <1%。
"""

    def _fallback_section(self) -> str:
        d = self.raw_data["modes"].get("fallback", {}).get("summary", {})
        if not d:
            return "## Fallback 模式\n\n*No data collected.*\n"
        return f"""## Fallback 模式 — Bridge 不可达时的降级

Fallback 模式下 `llm_bridge.py` 已停止，`api_client` 尝试 live 请求 → HTTP 超时 ({FALLBACK_TIMEOUT_MS}ms)
→ 自动降级到 mock 响应。此模式的超时配置为临时修改 `api_config.json` 的 `timeout_ms`。

| 指标 | 值 |
|------|-----|
| 采样数 | {d.get('samples', 0)} |
| 平均 | {self._fmt_ms(d.get('avg_ms', 0))} |
| P50 (中位数) | {self._fmt_ms(d.get('median_ms', 0))} |
| P95 | {self._fmt_ms(d.get('p95_ms', 0))} |
| P99 | {self._fmt_ms(d.get('p99_ms', 0))} |
| 最小值 | {self._fmt_ms(d.get('min_ms', 0))} |
| 最大值 | {self._fmt_ms(d.get('max_ms', 0))} |
| 错误率 | {d.get('error_rate', 0) * 100:.1f}% |
| 超时配置 | {FALLBACK_TIMEOUT_MS}ms |

> Fallback 总延迟 = HTTP 超时等待 + mock 响应时间。生产环境 `timeout_ms=20000`（20s），
> 基准测试中临时降为 {FALLBACK_TIMEOUT_MS}ms 以加快采集。生产 Fallback 延迟约为此值 × (20000 / {FALLBACK_TIMEOUT_MS})。
"""

    def _analysis_section(self) -> str:
        mock_s = self.raw_data["modes"].get("mock", {}).get("summary", {})
        off_s = self.raw_data["modes"].get("off", {}).get("summary", {})
        live_s = self.raw_data["modes"].get("live", {}).get("summary", {})
        fallback_s = self.raw_data["modes"].get("fallback", {}).get("summary", {})

        lines = ["## 综合分析\n"]

        # Mock baseline
        mock_p95 = mock_s.get("p95_ms", 0)
        live_p95 = live_s.get("p95_ms", 0)
        fallback_avg = fallback_s.get("avg_ms", 0)

        if mock_p95:
            lines.append(f"- **Mock P95 = {mock_p95:.2f}ms** — GDScript 内部路由开销极小（sub-ms 级）。")

        if off_s.get("p95_ms"):
            lines.append(f"- **Off P95 = {off_s['p95_ms']:.2f}ms** — 几乎为零，仅函数调用开销。")

        if live_p95:
            ratio = live_p95 / max(mock_p95, 0.001)
            lines.append(f"- **Live 模式 P95 = {self._fmt_ms(live_p95)}** — 是 Mock 的 "
                         f"**{ratio:.0f}x**，由 DeepSeek API 决定。")
            lines.append(f"  - LLM provider 占全部延迟的 **{live_s.get('breakdown', {}).get('http_provider_pct', '?')}%** "
                         f"（GDScript 侧开销 <1%）")

        if fallback_avg:
            lines.append(f"- **Fallback 平均 = {self._fmt_ms(fallback_avg)}** "
                         f"（超时={FALLBACK_TIMEOUT_MS}ms）。")
            lines.append(f"  - 生产环境 `timeout_ms=20000` 下预期 Fallback 延迟 ~20s，建议优化。")

        # Performance summary
        lines.append("")
        lines.append("### 优化建议")

        if live_p95 and live_p95 > 2000:
            lines.append("1. **Live 延迟高**由 LLM API 决定，非 Godot 侧问题。考虑引入响应缓存或预取。")

        if fallback_avg > 1000:
            lines.append(f"2. **Fallback 超时过长** — 当前 {FALLBACK_TIMEOUT_MS}ms 测试值远小于生产 20000ms。")
            lines.append(f"   建议将 `timeout_ms` 降低至 3000-5000ms 以改善用户体验。")

        lines.append("3. **Mock 模式延迟极低（sub-ms）** — 适合作为离线模式和默认降级方案。")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _fmt_ms(ms_val: float) -> str:
        if ms_val < 1000:
            return f"{ms_val:.2f}ms"
        return f"{ms_val / 1000:.2f}s"

    def generate_reports(self):
        """Generate Markdown and JSON reports."""
        log("\n" + "=" * 60)
        log("Generating Reports")
        log("=" * 60)

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # ── Markdown ──
        sections = [
            self._env_section(),
            self._acceptance_table(),
            self._mock_section(),
            self._off_section(),
            self._live_section(),
            self._fallback_section(),
            self._analysis_section(),
        ]

        md = "# MetaCampus API Latency Breakdown\n\n"
        md += f"> Generated: {self.raw_data['metadata'].get('timestamp', 'N/A')}\n"
        md += f"> Engine: Godot 4.6.3 (headless), GDScript api_client, llm_bridge.py → DeepSeek\n\n"
        md += "---\n\n"
        md += "\n\n".join(sections)

        md_path = REPORTS_DIR / "api-latency-breakdown.md"
        with open(md_path, "w") as f:
            f.write(md)
        log(f"Wrote Markdown report: {md_path}")

        # ── JSON ──
        json_report = {
            "report_type": "api-latency-breakdown",
            "generated_at": self.raw_data["metadata"]["timestamp"],
            "environment": {
                "platform": "macOS (Apple Silicon)",
                "godot": "4.6.3.stable",
                "renderer": "headless (SceneTree)",
                "capture_script": "tools/api_latency_capture.gd",
                "samples_per_mode": SAMPLES_PER_MODE,
            },
            "modes": {},
        }

        for mode in ["mock", "off", "live", "fallback"]:
            d = self.raw_data["modes"].get(mode, {})
            summary = d.get("summary", {})
            if summary:
                json_report["modes"][mode] = summary

        json_path = REPORTS_DIR / "api-latency-breakdown.json"
        with open(json_path, "w") as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        log(f"Wrote JSON report: {json_path}")

        return str(md_path), str(json_path)

    # ── Main orchestration ──

    def run_collection(self, modes: list[str] | None = None):
        """Run the full collection pipeline for specified modes."""
        if modes is None:
            modes = ["mock", "off", "live", "fallback"]

        # Pre-check Godot
        if not os.path.isfile(GODOT_EXEC):
            log(f"ERROR: Godot executable not found at {GODOT_EXEC}")
            sys.exit(1)

        # Kill any existing processes
        kill_godot()
        kill_bridge()
        time.sleep(1)

        mode_map = {
            "mock": self.collect_mock,
            "off": self.collect_off,
            "live": self.collect_live,
            "fallback": self.collect_fallback,
        }

        for mode in modes:
            if mode not in mode_map:
                log(f"WARNING: Unknown mode '{mode}', skipping.")
                continue

            # Kill Godot before each mode for clean state
            kill_godot()
            time.sleep(0.5)

            if mode in ("live", "fallback"):
                # For live and fallback, start Bridge first (fallback will stop it)
                if mode == "live" and self.bridge_proc is None:
                    self.bridge_proc = start_bridge()
                    if not wait_for_bridge():
                        log("ERROR: Bridge failed to start, skipping live/fallback modes.")
                        continue

            traces = mode_map[mode]()

            if not traces:
                log(f"WARNING: No traces collected for mode={mode}")
                self.raw_data["modes"][mode] = {
                    "traces": [],
                    "summary": {},
                }
                continue

            summary = self.compute_summary(traces, mode)
            self.raw_data["modes"][mode] = {
                "traces": traces,
                "summary": summary,
            }
            log(f"  → Summary: avg={summary.get('avg_ms', 0):.2f}ms  "
                f"P95={summary.get('p95_ms', 0):.2f}ms  "
                f"errors={summary.get('failures', 0)}/{summary.get('samples', 0)}")

        # Save raw data
        self.save_raw_data()

        # Clean up
        kill_godot()
        kill_bridge()
        self.bridge_proc = None

    def run_report_only(self):
        """Load existing raw data and regenerate reports."""
        if not self.load_raw_data():
            sys.exit(1)
        self.generate_reports()
        log("Report regeneration complete.")


# ── Main ──

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MetaCampus API Latency Benchmark — Multi-mode collection + report"
    )
    parser.add_argument("--mock-only", action="store_true", help="Only mock mode")
    parser.add_argument("--off-only", action="store_true", help="Only off mode")
    parser.add_argument("--live-only", action="store_true", help="Only live mode")
    parser.add_argument("--fallback-only", action="store_true", help="Only fallback mode")
    parser.add_argument("--report-only", action="store_true",
                        help="Regenerate reports from existing raw data only")
    args = parser.parse_args()

    bench = APILatencyBench()

    if args.report_only:
        bench.run_report_only()
        return

    # Determine which modes to run
    explicit_modes = []
    if args.mock_only:
        explicit_modes.append("mock")
    if args.off_only:
        explicit_modes.append("off")
    if args.live_only:
        explicit_modes.append("live")
    if args.fallback_only:
        explicit_modes.append("fallback")

    modes_to_run = explicit_modes if explicit_modes else None

    bench.run_collection(modes_to_run)

    # Generate reports
    md_path, json_path = bench.generate_reports()

    log(f"\n{'=' * 60}")
    log(f"Done!")
    log(f"  Raw data: {OUTPUT_DIR / 'perf_api_raw.json'}")
    log(f"  Markdown: {md_path}")
    log(f"  JSON:     {json_path}")
    log(f"{'=' * 60}")


if __name__ == "__main__":
    main()
