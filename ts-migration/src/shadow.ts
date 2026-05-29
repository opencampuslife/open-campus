import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";

// ── Schema ──────────────────────────────────────────────────────────────────

export interface ShadowReport {
  module: string;
  input_hash: string;
  python_output_hash: string;
  ts_output_hash: string;
  match: boolean;
  diff_truncated: string | null;
  timestamp: string;
}

export interface ShadowModuleConfig {
  enabled: boolean;
  module: string;
  compareFn: (input: unknown) => { python: unknown; ts: unknown };
}

export interface ShadowConfig {
  reportsDir: string;
  modules: Record<string, ShadowModuleConfig>;
}

// ── Stable hashing ──────────────────────────────────────────────────────────

export function stableJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const items = value.map(stableJson);
    return `[${items.join(",")}]`;
  }
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>).sort();
    const pairs = keys.map((k) => `${JSON.stringify(k)}:${stableJson((value as Record<string, unknown>)[k])}`);
    return `{${pairs.join(",")}}`;
  }
  return String(value);
}

export function hashJson(value: unknown): string {
  return createHash("sha256").update(stableJson(value), "utf-8").digest("hex").slice(0, 16);
}

// ── Diff / redaction ────────────────────────────────────────────────────────

const REDACT_PATTERNS: Array<RegExp> = [
  /api[_-]?key['"]?\s*[:=]\s*['"][^'"]+['"]/gi,
  /sk-[a-zA-Z0-9]{20,}/g,
  /bearer\s+[a-zA-Z0-9._-]{20,}/gi,
];

export function redactText(text: string): string {
  let result = text;
  for (const pattern of REDACT_PATTERNS) {
    result = result.replace(pattern, (m) => {
      const prefix = m.slice(0, Math.min(8, m.length));
      return `${prefix}…[REDACTED]`;
    });
  }
  return result;
}

export function computeDiff(python: unknown, ts: unknown): string | null {
  const pyStr = stableJson(python);
  const tsStr = stableJson(ts);
  if (pyStr === tsStr) return null;
  return redactText(`python:${pyStr}|ts:${tsStr}`);
}

export function truncateDiff(diff: string, maxBytes: number = 2048): string {
  if (Buffer.byteLength(diff, "utf-8") <= maxBytes) return diff;
  return diff.slice(0, maxBytes) + "\n… [TRUNCATED]";
}

// ── Timestamp ───────────────────────────────────────────────────────────────

export function isoTimestamp(): string {
  const now = new Date();
  const ms = now.getUTCMilliseconds();
  const micros = String(ms * 1000).padStart(6, "0");
  const iso = now.toISOString().replace(/\.\d{3}Z/, `.${micros}+00:00`);
  return iso;
}

// ── JSONL writer ────────────────────────────────────────────────────────────

export class ShadowWriter {
  private reportsDir: string;

  constructor(reportsDir: string) {
    this.reportsDir = reportsDir;
    mkdirSync(reportsDir, { recursive: true });
  }

  write(report: ShadowReport): void {
    const datePart = report.timestamp.slice(0, 10);
    const logFile = resolve(this.reportsDir, `shadow-${datePart}.jsonl`);
    mkdirSync(dirname(logFile), { recursive: true });
    appendFileSync(logFile, JSON.stringify(report) + "\n", "utf-8");
  }
}

// ── Main harness ────────────────────────────────────────────────────────────

export function runShadow(config: ShadowConfig, moduleName: string, input: unknown): void {
  const moduleCfg = config.modules[moduleName];
  if (!moduleCfg?.enabled) return;

  const inputHash = hashJson(input);

  let pythonResult: unknown;
  let tsResult: unknown;
  try {
    const result = moduleCfg.compareFn(input);
    pythonResult = result.python;
    tsResult = result.ts;
  } catch {
    return;
  }

  const pythonOutputHash = hashJson(pythonResult);
  const tsOutputHash = hashJson(tsResult);
  const match = pythonOutputHash === tsOutputHash;
  const diff = match ? null : truncateDiff(computeDiff(pythonResult, tsResult) ?? "");

  const report: ShadowReport = {
    module: moduleName,
    input_hash: inputHash,
    python_output_hash: pythonOutputHash,
    ts_output_hash: tsOutputHash,
    match,
    diff_truncated: diff,
    timestamp: isoTimestamp(),
  };

  const writer = new ShadowWriter(config.reportsDir);
  writer.write(report);
}
