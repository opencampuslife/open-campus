import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync, existsSync, rmSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { logLlmCall, redactPayload } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "llm_logger.json");

interface FixtureOutput {
  ok: boolean;
  result?: string;
  error?: string;
  message?: string;
}

interface FixtureCase {
  function: string;
  desc: string;
  input: Record<string, unknown>;
  output: FixtureOutput;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || b === null) return a === b;
  if (typeof a !== typeof b) return false;
  if (typeof a !== "object" || typeof b !== "object") return false;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  const aObj = a as Record<string, unknown>;
  const bObj = b as Record<string, unknown>;
  const aKeys = Object.keys(aObj).sort();
  const bKeys = Object.keys(bObj).sort();
  if (aKeys.length !== bKeys.length) return false;
  for (let i = 0; i < aKeys.length; i++) {
    if (aKeys[i] !== bKeys[i]) return false;
  }
  for (const key of aKeys) {
    if (!deepEqual(aObj[key], bObj[key])) return false;
  }
  return true;
}

// ── Golden Fixture Parity ──

describe("golden fixture parity", () => {
  it("parsed JSON line matches Python output for all fixtures", () => {
    for (const f of fixtures) {
      // Call logLlmCall, read file, compare parsed result
      const tmpRoot = join(tmpdir(), `llm_logger_fixture_${randomUUID()}`);
      mkdirSync(tmpRoot, { recursive: true });
      try {
        logLlmCall(tmpRoot, f.input);
        const logFile = join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl");
        const line = readFileSync(logFile, "utf-8").trim();
        const tsResult = JSON.parse(line);
        // Remove timestamp for comparison (dynamic)
        const expected = JSON.parse(f.output.result!);
        delete tsResult.created_at;
        delete expected.created_at;
        expect(deepEqual(tsResult, expected)).toBe(true);
      } finally {
        rmSync(tmpRoot, { recursive: true, force: true });
      }
    }
  });
});

// ── A: JSONL Record Snapshot ──

describe("A: JSONL record snapshot", () => {
  let tmpRoot: string;

  beforeEach(() => {
    tmpRoot = join(tmpdir(), `llm_logger_a_${randomUUID()}`);
    mkdirSync(tmpRoot, { recursive: true });
  });

  afterEach(() => {
    rmSync(tmpRoot, { recursive: true, force: true });
  });

  it("minimal success record has correct fields", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "你好" } });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("ok");
    expect(entry.request.message).toBe("你好");
    expect(entry).toHaveProperty("created_at");
    expect(typeof entry.created_at).toBe("string");
  });

  it("full success record preserves all fields", () => {
    logLlmCall(tmpRoot, {
      status: "ok",
      route: { provider: "deepseek", model: "deepseek-v4-flash" },
      request: { message: "学费多少", intent: "inquiry" },
      answer: "复读班学费9800元/学期",
      usage: { prompt_tokens: 150, completion_tokens: 50 },
    });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("ok");
    expect(entry.route.provider).toBe("deepseek");
    expect(entry.usage.prompt_tokens).toBe(150);
    expect(entry.answer).toBe("复读班学费9800元/学期");
  });

  it("error record preserves error field", () => {
    logLlmCall(tmpRoot, {
      status: "error",
      route: { provider: "deepseek" },
      error: "API timeout after 30s",
      request: { message: "test" },
    });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("error");
    expect(entry.error).toBe("API timeout after 30s");
  });

  it("redacts phone in input", () => {
    logLlmCall(tmpRoot, {
      status: "ok",
      request: { message: "我的手机13800138000" },
    });
    const entry = readEntry(tmpRoot);
    expect(entry.request.message).toContain("[REDACTED_PHONE]");
    expect(entry.request.message).not.toContain("13800138000");
  });

  it("redacts phone in answer", () => {
    logLlmCall(tmpRoot, {
      status: "ok",
      request: { message: "电话" },
      answer: "请致电13800138000联系",
    });
    const entry = readEntry(tmpRoot);
    expect(entry.answer).toContain("[REDACTED_PHONE]");
    expect(entry.answer).not.toContain("13800138000");
  });

  it("empty prompt preserved", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "" }, answer: "ok" });
    const entry = readEntry(tmpRoot);
    expect(entry.request.message).toBe("");
  });

  it("null metadata preserved", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "test" }, metadata: null });
    const entry = readEntry(tmpRoot);
    expect(entry.metadata).toBeNull();
  });

  it("missing optional fields omitted (not null)", () => {
    logLlmCall(tmpRoot, { status: "ok" });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("ok");
    expect(entry.request).toBeUndefined();
  });

  it("unicode Chinese preserved", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "我想报名复读班，请问学费多少？" } });
    const entry = readEntry(tmpRoot);
    expect(entry.request.message).toBe("我想报名复读班，请问学费多少？");
  });

  it("emoji preserved", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "😊欢迎咨询" } });
    const entry = readEntry(tmpRoot);
    expect(entry.request.message).toBe("😊欢迎咨询");
  });

  it("newline in prompt preserved", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "line1\nline2\nline3" } });
    const entry = readEntry(tmpRoot);
    expect(entry.request.message).toBe("line1\nline2\nline3");
  });

  it("timestamp has valid UTC ISO format", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "test" } });
    const entry = readEntry(tmpRoot);
    expect(entry.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/);
  });
});

// ── B: File Append Snapshot ──

describe("B: file append snapshot", () => {
  let tmpRoot: string;

  beforeEach(() => {
    tmpRoot = join(tmpdir(), `llm_logger_b_${randomUUID()}`);
    mkdirSync(tmpRoot, { recursive: true });
  });

  afterEach(() => {
    rmSync(tmpRoot, { recursive: true, force: true });
  });

  it("creates log file at correct path", () => {
    logLlmCall(tmpRoot, { status: "ok" });
    const logFile = join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl");
    expect(existsSync(logFile)).toBe(true);
  });

  it("one JSON line per call", () => {
    logLlmCall(tmpRoot, { status: "ok", id: 1 });
    logLlmCall(tmpRoot, { status: "ok", id: 2 });
    const lines = readFileSync(join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl"), "utf-8").trimEnd().split("\n");
    expect(lines.length).toBe(2);
  });

  it("append order matches call order", () => {
    logLlmCall(tmpRoot, { status: "ok", id: "first" });
    logLlmCall(tmpRoot, { status: "ok", id: "second" });
    const lines = readFileSync(join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl"), "utf-8").trimEnd().split("\n");
    const first = JSON.parse(lines[0]!);
    const second = JSON.parse(lines[1]!);
    expect(first.id).toBe("first");
    expect(second.id).toBe("second");
  });

  it("each line ends with newline (Python behavior)", () => {
    logLlmCall(tmpRoot, { status: "ok" });
    const raw = readFileSync(join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl"), "utf-8");
    expect(raw.endsWith("\n")).toBe(true);
  });

  it("each line is valid JSON", () => {
    logLlmCall(tmpRoot, { status: "ok", request: { message: "你好" } });
    const line = readFileSync(join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl"), "utf-8").trim();
    expect(() => JSON.parse(line)).not.toThrow();
  });
});

// ── C: Error Logging Snapshot ──

describe("C: error logging snapshot", () => {
  let tmpRoot: string;

  beforeEach(() => {
    tmpRoot = join(tmpdir(), `llm_logger_c_${randomUUID()}`);
    mkdirSync(tmpRoot, { recursive: true });
  });

  afterEach(() => {
    rmSync(tmpRoot, { recursive: true, force: true });
  });

  it("provider error recorded with error field", () => {
    logLlmCall(tmpRoot, {
      status: "error",
      route: { provider: "deepseek" },
      error: "HTTP 503: Service Unavailable",
      request: { message: "test" },
    });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("error");
    expect(entry.error).toBe("HTTP 503: Service Unavailable");
    expect(entry.route.provider).toBe("deepseek");
  });

  it("timeout error recorded", () => {
    logLlmCall(tmpRoot, {
      status: "error",
      route: { provider: "deepseek" },
      error: "API timeout after 30s",
      request: { message: "test" },
    });
    const entry = readEntry(tmpRoot);
    expect(entry.status).toBe("error");
    expect(entry.error).toContain("timeout");
  });
});

// ── D: No External Dependency Snapshot ──

describe("D: no external dependency snapshot", () => {
  it("source file imports only redactor (no gateway/provider/model_router/promptGuard)", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "llmLogger.ts"),
      "utf-8",
    );
    const forbidden = ["gateway", "provider_deepseek", "model_router", "promptGuard", "schemas"];
    for (const dep of forbidden) {
      expect(source).not.toContain(dep);
    }
  });

  it("imports redactor for redaction", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "llmLogger.ts"),
      "utf-8",
    );
    expect(source).toContain("redactor");
  });
});

// ── Helpers ──

function readEntry(tmpRoot: string): Record<string, unknown> {
  const logFile = join(tmpRoot, "data", "llm_logs", "llm_calls.jsonl");
  return JSON.parse(readFileSync(logFile, "utf-8").trim());
}
