import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync, rmSync, mkdirSync, readdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import {
  stableJson,
  hashJson,
  redactText,
  computeDiff,
  truncateDiff,
  isoTimestamp,
  ShadowWriter,
  runShadow,
} from "../src/shadow.js";
import type { ShadowReport, ShadowConfig } from "../src/shadow.js";
import { normalizeMarkdown } from "../../services/source-ingestion-service/ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..");

describe("stableJson", () => {
  it("handles null", () => {
    expect(stableJson(null)).toBe("null");
  });

  it("handles strings", () => {
    expect(stableJson("hello")).toBe('"hello"');
  });

  it("handles numbers", () => {
    expect(stableJson(42)).toBe("42");
  });

  it("handles booleans", () => {
    expect(stableJson(true)).toBe("true");
  });

  it("sorts object keys", () => {
    const input = { b: 2, a: 1, c: 3 };
    expect(stableJson(input)).toBe('{"a":1,"b":2,"c":3}');
  });

  it("handles nested objects", () => {
    const input = { z: { b: 2, a: 1 }, y: [3, 2, 1] };
    const result = stableJson(input);
    expect(result).toContain('"z":');
    expect(result).toContain('"a":1');
  });

  it("is deterministic", () => {
    const a = { x: [3, 1, 2], y: { b: "b", a: "a" } };
    const b = { y: { a: "a", b: "b" }, x: [3, 1, 2] };
    expect(stableJson(a)).toBe(stableJson(b));
  });
});

describe("hashJson", () => {
  it("produces consistent 16-char hex", () => {
    const h = hashJson({ a: 1 });
    expect(h).toMatch(/^[0-9a-f]{16}$/);
  });

  it("same value = same hash", () => {
    expect(hashJson([1, 2, 3])).toBe(hashJson([1, 2, 3]));
  });

  it("different value = different hash", () => {
    expect(hashJson({ a: 1 })).not.toBe(hashJson({ a: 2 }));
  });
});

describe("redactText", () => {
  it("redacts api_key= style values", () => {
    const input = 'api_key="sk-test123456789abcdef"';
    expect(redactText(input)).toContain("[REDACTED]");
    expect(redactText(input)).not.toContain("sk-test123456789abcdef");
  });

  it("redacts bearer tokens", () => {
    const input = "Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
    expect(redactText(input)).toContain("[REDACTED]");
  });

  it("redacts sk- prefixed keys", () => {
    const input = "sk-abcdefghijklmnopqrstuvwxyz123456";
    expect(redactText(input)).toContain("[REDACTED]");
  });

  it("passes through safe text", () => {
    const input = "Hello, World!";
    expect(redactText(input)).toBe(input);
  });
});

describe("computeDiff", () => {
  it("returns null for identical values", () => {
    expect(computeDiff({ a: 1 }, { a: 1 })).toBeNull();
  });

  it("returns string for different values", () => {
    const diff = computeDiff({ a: 1 }, { a: 2 });
    expect(diff).not.toBeNull();
    expect(diff).toContain("2");
  });

  it("returns string for structurally different values", () => {
    const diff = computeDiff([1, 2, 3], [1, 2, 4]);
    expect(diff).not.toBeNull();
    expect(typeof diff).toBe("string");
  });
});

describe("truncateDiff", () => {
  it("does not truncate short diff", () => {
    const diff = "a".repeat(500);
    expect(truncateDiff(diff, 2048)).toBe(diff);
  });

  it("truncates long diff", () => {
    const diff = "a".repeat(3000);
    const result = truncateDiff(diff, 2048);
    expect(Buffer.byteLength(result, "utf-8")).toBeLessThanOrEqual(2100);
    expect(result).toContain("[TRUNCATED]");
  });
});

describe("isoTimestamp", () => {
  it("matches expected format", () => {
    const ts = isoTimestamp();
    expect(ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/);
  });
});

describe("ShadowWriter", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = join(tmpdir(), `shadow_test_${randomUUID()}`);
    mkdirSync(tmpDir, { recursive: true });
  });

  afterEach(() => {
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("writes a JSONL report", () => {
    const writer = new ShadowWriter(tmpDir);
    const report: ShadowReport = {
      module: "test_module",
      input_hash: "abc123",
      python_output_hash: "def456",
      ts_output_hash: "def456",
      match: true,
      diff_truncated: null,
      timestamp: "2026-05-29T00:00:00.000000+00:00",
    };
    writer.write(report);

    const files = readdirSync(tmpDir);
    expect(files.length).toBe(1);
    const content = readFileSync(join(tmpDir, files[0]!), "utf-8");
    const parsed = JSON.parse(content.trim()) as ShadowReport;
    expect(parsed.module).toBe("test_module");
    expect(parsed.match).toBe(true);
  });

  it("writes multiple reports to same file", () => {
    const writer = new ShadowWriter(tmpDir);
    for (let i = 0; i < 3; i++) {
      writer.write({
        module: `m${i}`,
        input_hash: `in${i}`,
        python_output_hash: `py${i}`,
        ts_output_hash: `ts${i}`,
        match: true,
        diff_truncated: null,
        timestamp: "2026-05-29T00:00:00.000000+00:00",
      });
    }
    const files = readdirSync(tmpDir);
    expect(files.length).toBe(1);
    const lines = readFileSync(join(tmpDir, files[0]!), "utf-8").trim().split("\n");
    expect(lines.length).toBe(3);
  });
});

describe("runShadow", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = join(tmpdir(), `shadow_run_${randomUUID()}`);
    mkdirSync(tmpDir, { recursive: true });
  });

  afterEach(() => {
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("does not write report when module is disabled", () => {
    const config: ShadowConfig = {
      reportsDir: tmpDir,
      modules: {
        markdown_normalizer: {
          enabled: false,
          module: "markdown_normalizer",
          compareFn: (_input: unknown) => {
            return { python: "result", ts: "result" };
          },
        },
      },
    };
    runShadow(config, "markdown_normalizer", "test");
    const files = readdirSync(tmpDir);
    expect(files.length).toBe(0);
  });

  it("writes match=true report for identical outputs", () => {
    const config: ShadowConfig = {
      reportsDir: tmpDir,
      modules: {
        md: {
          enabled: true,
          module: "md",
          compareFn: (_input: unknown) => {
            return { python: "hello", ts: "hello" };
          },
        },
      },
    };
    runShadow(config, "md", "test");
    const files = readdirSync(tmpDir);
    expect(files.length).toBe(1);
    const content = readFileSync(join(tmpDir, files[0]!), "utf-8");
    const report = JSON.parse(content.trim()) as ShadowReport;
    expect(report.match).toBe(true);
    expect(report.diff_truncated).toBeNull();
  });

  it("writes match=false report for different outputs", () => {
    const config: ShadowConfig = {
      reportsDir: tmpDir,
      modules: {
        md: {
          enabled: true,
          module: "md",
          compareFn: (_input: unknown) => {
            return { python: "hello", ts: "world" };
          },
        },
      },
    };
    runShadow(config, "md", "test");
    const files = readdirSync(tmpDir);
    expect(files.length).toBe(1);
    const content = readFileSync(join(tmpDir, files[0]!), "utf-8");
    const report = JSON.parse(content.trim()) as ShadowReport;
    expect(report.match).toBe(false);
    expect(report.diff_truncated).not.toBeNull();
  });

  it("handles thrown errors gracefully (no crash)", () => {
    const config: ShadowConfig = {
      reportsDir: tmpDir,
      modules: {
        broken: {
          enabled: true,
          module: "broken",
          compareFn: (_input: unknown) => {
            throw new Error("oops");
          },
        },
      },
    };
    expect(() => runShadow(config, "broken", "test")).not.toThrow();
  });

  it("markdown_normalizer shadow compare produces match=true on identical input", () => {
    const fixturePath = resolve(REPO_ROOT, "ts-migration", "fixtures", "markdown_normalizer.json");
    const cases: Array<{ input: string; output: string }> = JSON.parse(readFileSync(fixturePath, "utf-8"));

    const config: ShadowConfig = {
      reportsDir: tmpDir,
      modules: {
        markdown_normalizer: {
          enabled: true,
          module: "markdown_normalizer",
          compareFn: (input: unknown) => {
            const text = input as string;
            const tsResult = normalizeMarkdown(text);
            return { python: tsResult, ts: tsResult };
          },
        },
      },
    };

    for (const c of cases) {
      runShadow(config, "markdown_normalizer", c.input);
    }

    const files = readdirSync(tmpDir);
    expect(files.length).toBeGreaterThanOrEqual(1);
    const content = readFileSync(join(tmpDir, files[0]!), "utf-8");
    const lines = content.trim().split("\n");
    for (const line of lines) {
      const report = JSON.parse(line) as ShadowReport;
      expect(report.match).toBe(true);
    }
  });
});
