#!/usr/bin/env python3
"""MetaCampus Perf Baseline — NPC梯度FPS/P95/API/Smoke基线采集

Usage:
    python tools/perf_baseline.py                   # Full collection
    python tools/perf_baseline.py --npc-only         # Only NPC gradient tests
    python tools/perf_baseline.py --api-only         # Only API latency tests
    python tools/perf_baseline.py --smoke-only       # Only smoke timing tests
    python tools/perf_baseline.py --report-only      # Only regenerate report from existing data

Outputs:
    tools/perf_output/               # Raw CSV data from GDScript
    reports/perf-baseline.md         # Final report
    reports/perf-baseline-data.csv   # Aggregated data table
"""

import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
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
HARNESS_READY_TIMEOUT = 15  # seconds

NPC_GRADIENTS = [10, 50, 100, 300]

SAMPLE_DURATION = 35  # seconds (≥30s per requirement)
WARMUP_DURATION = 3

SMOKE_SCRIPTS = {
    "G2": TOOLS_DIR / "smoke_g2.py",
    "G3": TOOLS_DIR / "smoke_g3.py",
    "G4": TOOLS_DIR / "smoke_g4.py",
}

# API test queries
API_TEST_QUERIES = [
    ("mock_admission", "/api/ask?q=" + urllib.parse.quote("报名需要哪些材料")),
    ("mock_default", "/api/ask?q=" + urllib.parse.quote("今天天气怎么样")),
    ("high_risk_guarantee", "/api/ask?q=" + urllib.parse.quote("能不能保证录取")),
    ("high_risk_backdoor", "/api/ask?q=" + urllib.parse.quote("走后门入学")),
    ("mock_materials", "/api/ask?q=" + urllib.parse.quote("需要哪些报名材料")),
    ("mock_transfer", "/api/ask?q=" + urllib.parse.quote("如何办理转学")),
    ("mock_scholarship", "/api/ask?q=" + urllib.parse.quote("奖学金申请条件")),
    ("mock_deadline", "/api/ask?q=" + urllib.parse.quote("报名截止时间")),
    ("high_risk_quota", "/api/ask?q=" + urllib.parse.quote("内部名额")),
    ("high_risk_special", "/api/ask?q=" + urllib.parse.quote("特殊照顾")),
    ("mock_curriculum", "/api/ask?q=" + urllib.parse.quote("课程安排")),
    ("mock_tuition", "/api/ask?q=" + urllib.parse.quote("学费多少")),
    ("mock_dormitory", "/api/ask?q=" + urllib.parse.quote("宿舍条件")),
    ("mock_teacher", "/api/ask?q=" + urllib.parse.quote("师资力量")),
    ("high_risk_100pct", "/api/ask?q=" + urllib.parse.quote("百分百录取")),
    ("mock_graduation", "/api/ask?q=" + urllib.parse.quote("毕业去向")),
    ("mock_exam", "/api/ask?q=" + urllib.parse.quote("考试安排")),
    ("mock_activity", "/api/ask?q=" + urllib.parse.quote("校园活动")),
    ("mock_insurance", "/api/ask?q=" + urllib.parse.quote("学生保险")),
    ("mock_library", "/api/ask?q=" + urllib.parse.quote("图书馆开放时间")),
]


# ── Helpers ──

def log(msg: str):
    print(f"[perf-baseline] {msg}")


def http_get(path: str, timeout: int = 5) -> dict:
    url = TEST_HARNESS_BASE + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def wait_for_harness(timeout: int = HARNESS_READY_TIMEOUT) -> bool:
    log(f"Waiting for TestHarness at {TEST_HARNESS_BASE}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = http_get("/health", timeout=2)
            if r.get("status") == "ok":
                log("TestHarness is ready.")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    log("ERROR: TestHarness did not become ready.")
    return False


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


def start_godot(args: list[str], headless: bool = True, env: dict = None) -> subprocess.Popen:
    """Start Godot with given extra args, return Popen."""
    cmd = [GODOT_EXEC]
    if headless:
        cmd.append("--headless")
    cmd += ["--path", str(PROJECT_DIR)] + args
    log("Starting: " + " ".join(str(c) for c in cmd))
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=proc_env
    )
    return proc


# ── Test Phases ──

class PerfBaseline:
    """Orchestrates all performance baseline tests."""

    def __init__(self):
        self.results = {
            "npc_gradient": {},
            "api_latency": {},
            "smoke_timing": {},
            "json_load_timing": {},
        }
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Phase 1: NPC Gradient ──

    def run_npc_gradient(self) -> bool:
        """Run Godot headless with perf_capture.gd for each NPC gradient."""
        log("=" * 60)
        log("Phase 1: NPC Gradient Performance")
        log("=" * 60)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for n in NPC_GRADIENTS:
            log(f"\n--- NPC={n} ---")

            # Clean up previous output
            for f in OUTPUT_DIR.glob(f"perf_npc_{n}.csv"):
                f.unlink()
            for f in OUTPUT_DIR.glob(f"perf_summary_{n}.json"):
                f.unlink()

            env = os.environ.copy()
            env["PERF_OUTPUT_DIR"] = str(OUTPUT_DIR)

            proc = start_godot(
                ["--script", "tools/perf_capture.gd", f"--npc={n}"],
                headless=True,
                env=env
            )

            try:
                stdout, stderr = proc.communicate(timeout=SAMPLE_DURATION + WARMUP_DURATION + 15)
                log(stdout[-2000:] if len(stdout) > 2000 else stdout)
                if stderr:
                    log(f"STDERR (last 1k): {stderr[-1000:]}")
            except subprocess.TimeoutExpired:
                log(f"WARNING: Godot timed out for NPC={n}, killing...")
                proc.kill()
                stdout, stderr = proc.communicate(timeout=5)
                log(stdout[-1000:] if len(stdout) > 1000 else stdout)
            except FileNotFoundError:
                log(f"ERROR: Godot executable not found at {GODOT_EXEC}")
                return False

            # Read summary
            summary_path = OUTPUT_DIR / f"perf_summary_{n}.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    summary = json.load(f)
                self.results["npc_gradient"][n] = summary
                log(f"  → FPS avg={summary.get('fps_avg', '?')}, "
                    f"P95 process={summary.get('process_time_us_p95', '?')}us")

                # Also capture JSON timings (from first run)
                if not self.results["json_load_timing"] and "json_timings" in summary:
                    self.results["json_load_timing"] = summary["json_timings"]
            else:
                log(f"WARNING: No summary file for NPC={n} at {summary_path}")
                # Try reading from stdout
                if stdout:
                    self._parse_summary_from_stdout(stdout, n)

        return True

    def _parse_summary_from_stdout(self, stdout: str, n: int):
        """Fallback: parse JSON summary from Godot stdout."""
        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.results["npc_gradient"][n] = json.loads(line)
                    return
                except json.JSONDecodeError:
                    pass

    # ── Phase 2: API Latency ──

    def run_api_latency(self) -> bool:
        """Measure API round-trip latency via TestHarness HTTP."""
        log("\n" + "=" * 60)
        log("Phase 2: API Latency")
        log("=" * 60)

        # Ensure mock mode
        r = http_get("/api/mode?set=mock")
        log(f"Set mode: {r}")

        time.sleep(0.2)

        latencies = []
        failures = 0

        for name, path in API_TEST_QUERIES:
            for _ in range(3):  # 3 samples per query = 60 total
                t0 = time.time()
                r = http_get(path, timeout=10)
                elapsed_ms = (time.time() - t0) * 1000

                if "_error" in r:
                    failures += 1
                    log(f"  ❌ {name}: ERROR {r['_error']}")
                else:
                    latencies.append(elapsed_ms)

                time.sleep(0.05)  # brief cooldown

        if latencies:
            latencies.sort()
            n = len(latencies)
            self.results["api_latency"] = {
                "samples": n,
                "failures": failures,
                "min_ms": round(latencies[0], 2),
                "p50_ms": round(latencies[int(n * 0.50)], 2),
                "p95_ms": round(latencies[int(n * 0.95)], 2),
                "p99_ms": round(latencies[int(n * 0.99)], 2),
                "max_ms": round(latencies[-1], 2),
                "avg_ms": round(sum(latencies) / n, 2),
                "all_latencies_ms": [round(x, 2) for x in latencies],
            }
            log(f"API latency: P50={self.results['api_latency']['p50_ms']}ms "
                f"P95={self.results['api_latency']['p95_ms']}ms "
                f"(samples={n})")
        else:
            log("ERROR: No successful API latency measurements.")

        # Persist results
        if self.results["api_latency"]:
            api_path = OUTPUT_DIR / "perf_api_latency.json"
            with open(api_path, "w") as f:
                # Strip large all_latencies_ms for storage
                persist = {k: v for k, v in self.results["api_latency"].items() if k != "all_latencies_ms"}
                json.dump(persist, f, indent=2)

        return len(latencies) > 0

    # ── Phase 3: Smoke Timing ──

    def run_smoke_timing(self) -> bool:
        """Run each smoke test script and measure duration."""
        log("\n" + "=" * 60)
        log("Phase 3: Smoke Test Timing")
        log("=" * 60)

        all_ok = True
        for phase, script_path in SMOKE_SCRIPTS.items():
            if not script_path.exists():
                log(f"WARNING: {script_path} not found, skipping.")
                continue

            log(f"\n--- {phase} Smoke Test ---")
            t0 = time.time()

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=120
            )
            elapsed = round(time.time() - t0, 2)

            passed = result.returncode == 0
            self.results["smoke_timing"][phase] = {
                "duration_sec": elapsed,
                "passed": passed,
                "returncode": result.returncode,
            }

            status = "✅ PASS" if passed else "❌ FAIL"
            log(f"  {phase}: {elapsed}s {status}")

            if not passed:
                all_ok = False
                log(f"  stdout: {result.stdout[-500:]}")
                log(f"  stderr: {result.stderr[-500:]}")

        # Persist results
        if self.results["smoke_timing"]:
            smoke_path = OUTPUT_DIR / "perf_smoke_timing.json"
            with open(smoke_path, "w") as f:
                json.dump(self.results["smoke_timing"], f, indent=2)

        return all_ok

    # ── Data Export ──

    def export_aggregated_csv(self) -> Path:
        """Export aggregated results as CSV."""
        csv_path = REPORTS_DIR / "perf-baseline-data.csv"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        rows = []
        # NPC gradient rows
        for n, data in sorted(self.results["npc_gradient"].items()):
            rows.append({
                "test": f"npc_gradient_{n}",
                "npc_count": n,
                "metric": "fps_avg",
                "value": data.get("fps_avg", ""),
            })
            for metric in ["process_time_us_p50", "process_time_us_p95", "process_time_us_p99",
                           "physics_time_us_p50", "physics_time_us_p95", "physics_time_us_p99",
                           "fps_min", "spike_frequency", "memory_end_bytes"]:
                rows.append({
                    "test": f"npc_gradient_{n}",
                    "npc_count": n,
                    "metric": metric,
                    "value": data.get(metric, ""),
                })

        # API latency rows
        api = self.results.get("api_latency", {})
        for metric in ["samples", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"]:
            rows.append({
                "test": "api_latency",
                "npc_count": "",
                "metric": metric,
                "value": api.get(metric, ""),
            })

        # Smoke timing rows
        for phase, data in self.results.get("smoke_timing", {}).items():
            rows.append({
                "test": f"smoke_{phase}",
                "npc_count": "",
                "metric": "duration_sec",
                "value": data.get("duration_sec", ""),
            })

        # JSON load timing rows
        for file_name, timings in self.results.get("json_load_timing", {}).items():
            for stage in ["cold_load_us", "parse_us", "hot_load_us"]:
                rows.append({
                    "test": f"json_load_{file_name}",
                    "npc_count": "",
                    "metric": stage,
                    "value": timings.get(stage, ""),
                })

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["test", "npc_count", "metric", "value"])
            writer.writeheader()
            writer.writerows(rows)

        log(f"Wrote aggregated CSV: {csv_path}")
        return csv_path

    # ── Report Generation ──

    def generate_report(self) -> str:
        """Generate the markdown baseline report."""
        log("\n" + "=" * 60)
        log("Generating Baseline Report")
        log("=" * 60)

        report_path = REPORTS_DIR / "perf-baseline.md"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        sections = [
            self._env_section(),
            self._npc_gradient_section(),
            self._api_latency_section(),
            self._smoke_timing_section(),
            self._json_load_section(),
            self._conclusion_section(),
        ]

        report = "# MetaCampus Perf Baseline Report\n\n"
        report += f"> Generated: {self.timestamp}\n"
        report += f"> Engine: Godot 4.6.3 (GL Compatibility), Pure GDScript\n\n"
        report += "---\n\n"
        report += "\n\n".join(sections)

        with open(report_path, "w") as f:
            f.write(report)

        log(f"Wrote report: {report_path}")
        return str(report_path)

    def _env_section(self) -> str:
        npc_data = self.results.get("npc_gradient", {})
        first_npc = next(iter(npc_data.values()), {})
        samples = first_npc.get("samples", 0)

        return f"""## 环境信息

| 项目 | 值 |
|------|-----|
| 主机 | macOS (Apple Silicon) |
| Godot 版本 | 4.6.3.stable |
| 渲染器 | GL Compatibility |
| 运行模式 | headless (CPU profiling) |
| 采集脚本 | `tools/perf_capture.gd` |
| 采样时长 | {SAMPLE_DURATION}s / run |
| 每轮样本数 | ~{samples} frames |
| NPC 梯度 | {', '.join(str(n) for n in NPC_GRADIENTS)} |
| 基线状态 | **纯 GDScript** (GDExtension 迁移前) |
"""

    def _npc_gradient_section(self) -> str:
        if not self.results["npc_gradient"]:
            return "## NPC 梯度性能\n\n*No data collected.*"

        rows = []
        for n in NPC_GRADIENTS:
            d = self.results["npc_gradient"].get(n, {})
            rows.append(f"| {n} | {d.get('fps_avg', 'N/A')} | {d.get('fps_min', 'N/A')} "
                        f"| {d.get('process_time_us_p50', 'N/A')} | {d.get('process_time_us_p95', 'N/A')} "
                        f"| {d.get('process_time_us_p99', 'N/A')} "
                        f"| {d.get('physics_time_us_p95', 'N/A')} "
                        f"| {d.get('spike_frequency', 'N/A')} "
                        f"| {self._fmt_mem(d.get('memory_end_bytes', 0))} |")

        header = """## NPC 梯度性能对比

| NPC 数 | FPS avg | FPS min | 帧处理 P50(μs) | 帧处理 P95(μs) | 帧处理 P99(μs) | Physics P95(μs) | Spike 频率 | 内存 |
|--------|---------|---------|----------------|----------------|----------------|-----------------|------------|------|"""
        return header + "\n" + "\n".join(rows) + "\n"

    def _api_latency_section(self) -> str:
        d = self.results.get("api_latency", {})
        if not d:
            return "## API 延迟\n\n*No data collected.*"

        samples = d.get("samples", 0)
        failures = d.get("failures", 0)
        return f"""## API 延迟统计 (mock mode)

| 指标 | 值 |
|------|-----|
| 采样数 | {samples} |
| 失败数 | {failures} |
| 平均 (ms) | {d.get('avg_ms', 'N/A')} |
| P50 (ms) | {d.get('p50_ms', 'N/A')} |
| P95 (ms) | {d.get('p95_ms', 'N/A')} |
| P99 (ms) | {d.get('p99_ms', 'N/A')} |
| 最小 (ms) | {d.get('min_ms', 'N/A')} |
| 最大 (ms) | {d.get('max_ms', 'N/A')} |

> API 通过 TestHarness HTTP 端点 (/api/ask) 测量，mode=mock。
> 包括 HTTP 序列化/反序列化 + GDScript 处理开销。
"""

    def _smoke_timing_section(self) -> str:
        d = self.results.get("smoke_timing", {})
        if not d:
            return "## Smoke 测试耗时\n\n*No data collected.*"

        rows = []
        total_time = 0
        all_passed = True
        for phase in ["G2", "G3", "G4"]:
            data = d.get(phase, {})
            if data:
                sec = data.get("duration_sec", 0)
                passed = data.get("passed", False)
                status = "✅" if passed else "❌"
                rows.append(f"| {phase} | {sec}s | {status} |")
                total_time += sec
                if not passed:
                    all_passed = False

        header = f"""## Smoke 测试全量耗时

| Phase | 耗时 | 结果 |
|-------|------|------|"""
        footer = f"\n| **合计** | **{total_time:.1f}s** | {'✅ All PASS' if all_passed else '❌ Has failures'} |"
        return header + "\n" + "\n".join(rows) + footer + "\n"

    def _json_load_section(self) -> str:
        d = self.results.get("json_load_timing", {})
        if not d:
            return "## JSON 配置加载耗时\n\n*No data collected.*"

        rows = []
        for file_name, timings in sorted(d.items()):
            cold = timings.get("cold_load_us", 0)
            parse = timings.get("parse_us", 0)
            hot = timings.get("hot_load_us", 0)
            rows.append(f"| `{file_name}.json` | {cold}μs | {parse}μs | {hot}μs |")

        return """## JSON 配置加载耗时

| 文件 | 冷加载(μs) | JSON解析(μs) | 热加载(μs) |
|------|-----------|-------------|-----------|
""" + "\n".join(rows) + "\n"

    def _conclusion_section(self) -> str:
        """Generate conclusion from collected data."""
        npc_data = self.results.get("npc_gradient", {})

        if not npc_data:
            return "## 结论\n\n*Insufficient data for conclusion.*"

        # Detect scaling trend
        p95_10 = npc_data.get(10, {}).get("process_time_us_p95", 0)
        p95_300 = npc_data.get(300, {}).get("process_time_us_p95", 0)

        lines = ["## 结论\n"]

        if p95_10 > 0 and p95_300 > 0:
            ratio = p95_300 / max(p95_10, 1)
            lines.append(f"- **NPC 规模缩放**: 从 10 NPC → 300 NPC, 帧处理 P95 从 **{p95_10}μs** "
                         f"增长到 **{p95_300}μs** ({ratio:.1f}x)。")
            if ratio < 10:
                lines.append("  - 缩放效率较好 (< 30x NPC 增长对应 < 10x 开销增长)")
            else:
                lines.append("  - 存在超线性增长风险，建议优化 NPC 批处理")

        # Memory trend
        mem_10 = npc_data.get(10, {}).get("memory_end_bytes", 0)
        mem_300 = npc_data.get(300, {}).get("memory_end_bytes", 0)
        if mem_10 > 0 and mem_300 > 0:
            mem_delta = mem_300 - mem_10
            lines.append(f"- **内存增长**: 10→300 NPC 内存增量 {self._fmt_mem(mem_delta)} "
                         f"(每 NPC ~{int(mem_delta / 290)} bytes)")

        # Spike analysis
        spike_300 = npc_data.get(300, {}).get("spike_frequency", 0)
        spike_10 = npc_data.get(10, {}).get("spike_frequency", 0)
        if spike_300 and spike_10:
            lines.append(f"- **帧时间抖动**: 300 NPC spike 频率 {spike_300:.4f} "
                         f"(10 NPC: {spike_10:.4f})")

        # API baseline
        api = self.results.get("api_latency", {})
        if api:
            lines.append(f"- **API P95 延迟**: {api.get('p95_ms', '?')}ms (mock mode, "
                         f"{api.get('samples', 0)} samples)")

        # Smoke baseline
        smoke = self.results.get("smoke_timing", {})
        if smoke:
            total = sum(d.get("duration_sec", 0) for d in smoke.values())
            all_pass = all(d.get("passed", False) for d in smoke.values())
            lines.append(f"- **Smoke 全量耗时**: {total:.1f}s ({'全部通过' if all_pass else '有失败'})")

        lines.append(f"\n> 此报告作为 **GDExtension 迁移基线**。")
        lines.append("> GDExtension 迁移后需对比此基线，P95 帧处理改善 ≥30% 方可通过准入。")

        return "\n".join(lines)

    @staticmethod
    def _fmt_mem(bytes_val) -> str:
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024**2:
            return f"{bytes_val / 1024:.1f} KB"
        else:
            return f"{bytes_val / 1024**2:.1f} MB"


# ── Main ──

def main():
    import urllib.parse  # for API path encoding

    parser = argparse.ArgumentParser(
        description="MetaCampus Perf Baseline Collector"
    )
    parser.add_argument("--npc-only", action="store_true", help="Only NPC gradient tests")
    parser.add_argument("--api-only", action="store_true", help="Only API latency tests")
    parser.add_argument("--smoke-only", action="store_true", help="Only smoke timing tests")
    parser.add_argument("--report-only", action="store_true",
                        help="Regenerate report from existing data only")
    parser.add_argument("--skip-npc", action="store_true", help="Skip NPC gradient tests")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke timing tests")
    args = parser.parse_args()

    baseline = PerfBaseline()

    # Pre-check
    if not GODOT_EXEC or not os.path.isfile(GODOT_EXEC):
        log(f"ERROR: Godot executable not found at {GODOT_EXEC}")
        sys.exit(1)

    # ── Phase 1: NPC Gradient ──
    if not args.api_only and not args.smoke_only and not args.report_only and not args.skip_npc:
        kill_godot()
        time.sleep(1)
        ok = baseline.run_npc_gradient()
        if not ok:
            log("WARNING: NPC gradient tests had issues, continuing...")
        kill_godot()
    elif args.report_only:
        log("Loading existing data from output dir...")
        for n in NPC_GRADIENTS:
            summary_path = OUTPUT_DIR / f"perf_summary_{n}.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    baseline.results["npc_gradient"][n] = json.load(f)
                    if "json_timings" in baseline.results["npc_gradient"][n]:
                        baseline.results["json_load_timing"] = \
                            baseline.results["npc_gradient"][n]["json_timings"]
                log(f"  Loaded NPC={n}")
            else:
                log(f"  WARNING: No data for NPC={n}")

        # Load API latency
        api_path = OUTPUT_DIR / "perf_api_latency.json"
        if api_path.exists():
            with open(api_path) as f:
                baseline.results["api_latency"] = json.load(f)
            log(f"  Loaded API latency data")

        # Load smoke timing
        smoke_path = OUTPUT_DIR / "perf_smoke_timing.json"
        if smoke_path.exists():
            with open(smoke_path) as f:
                baseline.results["smoke_timing"] = json.load(f)
            log(f"  Loaded smoke timing data")

    # ── Phase 2+3: API Latency + Smoke (need running Godot) ──
    if not args.npc_only and not args.report_only:
        kill_godot()
        time.sleep(0.5)

        # Start Godot (non-headless for HTTP test harness to work properly)
        log("Starting Godot with display for API/smoke tests...")
        proc = start_godot([], headless=False)

        if wait_for_harness():
            if not args.skip_smoke and not args.npc_only and not args.api_only:
                # Smoke first (uses clean state)
                baseline.run_smoke_timing()

            if not args.npc_only:
                baseline.run_api_latency()
        else:
            log("ERROR: TestHarness not reachable. Skipping API and smoke tests.")

        kill_godot()
        time.sleep(1)

    # ── Export + Report ──
    baseline.export_aggregated_csv()
    report_path = baseline.generate_report()

    log(f"\n{'=' * 60}")
    log(f"Done! Report: {report_path}")
    log(f"{'=' * 60}")


if __name__ == "__main__":
    import argparse
    main()
