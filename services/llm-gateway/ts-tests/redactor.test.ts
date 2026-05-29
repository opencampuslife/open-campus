import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { redactText, redactPayload } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "redactor.json");

interface FixtureOutput {
  ok: boolean;
  result?: unknown;
  error?: string;
  message?: string;
}

interface FixtureCase {
  function: string;
  desc: string;
  input: unknown;
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

function runTs(f: FixtureCase): FixtureOutput {
  try {
    const fn = f.function;
    const input = f.input;

    if (fn === "redact_text") {
      const result = redactText(input as string);
      return { ok: true, result };
    }

    if (fn === "redact_payload") {
      const result = redactPayload(input);
      return { ok: true, result };
    }

    return { ok: false, error: "UnknownFunction", message: `Unknown function: ${fn}` };
  } catch (e: unknown) {
    const err = e as Error;
    return {
      ok: false,
      error: err.name ?? err.constructor.name,
      message: err.message,
    };
  }
}

// --- Golden Fixture Parity ---

describe("golden fixture parity", () => {
  it("matches stored golden JSON output for all fixtures", () => {
    for (const f of fixtures) {
      const tsResult = runTs(f);
      if (f.output.ok) {
        expect(tsResult.ok).toBe(true);
        expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
        // String results must be byte-level equal
        if (typeof f.output.result === "string" && typeof tsResult.result === "string") {
          expect(tsResult.result).toBe(f.output.result);
        }
      } else {
        expect(tsResult.ok).toBe(false);
        expect(tsResult.error).toBe(f.output.error);
      }
    }
  });
});

// --- A: Redaction Output Snapshot ---

describe("A: redaction output snapshot", () => {
  it("手机号 redacted", () => {
    const result = redactText("我的手机号是13800138000");
    expect(result).toBe("我的手机号是[REDACTED_PHONE]");
  });

  it("API key redacted", () => {
    const result = redactText("sk-abc123def456ghi789");
    expect(result).toBe("[REDACTED_API_KEY]");
  });

  it("多规则同时命中", () => {
    const result = redactText("我的手机13800138000和密钥sk-abc123def456ghi");
    expect(result).toBe("我的手机[REDACTED_PHONE]和密钥[REDACTED_API_KEY]");
  });

  it("多个手机号", () => {
    const result = redactText("13800138000和13912345678都是手机号");
    expect(result).toBe("[REDACTED_PHONE]和[REDACTED_PHONE]都是手机号");
  });

  it("换行文本 preserves newlines", () => {
    const result = redactText("电话：13800138000\n邮箱：test@example.com");
    expect(result).toBe("电话：[REDACTED_PHONE]\n邮箱：test@example.com");
  });

  it("空字符串 unchanged", () => {
    expect(redactText("")).toBe("");
  });

  it("仅空白 unchanged", () => {
    expect(redactText("   ")).toBe("   ");
  });

  it("无敏感信息 unchanged", () => {
    expect(redactText("你好，今天天气不错")).toBe("你好，今天天气不错");
  });

  it("已经脱敏 unchanged", () => {
    expect(redactText("我的手机是[REDACTED_PHONE]和sk-[REDACTED_API_KEY]"))
      .toBe("我的手机是[REDACTED_PHONE]和sk-[REDACTED_API_KEY]");
  });

  it("手机号不足11位 unchanged", () => {
    expect(redactText("1380013800不是完整手机号")).toBe("1380013800不是完整手机号");
  });

  it("手机号前有数字 unchanged", () => {
    expect(redactText("数字113800138000包含边界")).toBe("数字113800138000包含边界");
  });

  it("手机号后有数字 unchanged", () => {
    expect(redactText("手机号138001380001后有多余数字")).toBe("手机号138001380001后有多余数字");
  });

  it("API key短于8位 unchanged", () => {
    expect(redactText("sk-abcde不匹配")).toBe("sk-abcde不匹配");
  });
});

// --- B: Rule Hit Snapshot ---

describe("B: rule hit snapshot", () => {
  function countHits(text: string): { phone: number; key: number } {
    const phoneMatches = text.match(/(?<!\d)1[3-9]\d{9}(?!\d)/g);
    const keyMatches = text.match(/sk-[A-Za-z0-9]{8,}/g);
    return {
      phone: (phoneMatches ?? []).length,
      key: (keyMatches ?? []).length,
    };
  }

  it("手机号 text has 1 phone hit before redaction", () => {
    const hits = countHits("我的手机号是13800138000");
    expect(hits.phone).toBe(1);
    expect(hits.key).toBe(0);
  });

  it("多个手机号 has 2 phone hits", () => {
    const hits = countHits("13800138000和13912345678");
    expect(hits.phone).toBe(2);
  });

  it("API key text has 1 key hit", () => {
    const hits = countHits("sk-abc123def456ghi789");
    expect(hits.key).toBe(1);
    expect(hits.phone).toBe(0);
  });

  it("多规则同时命中 has 1 phone + 1 key hit", () => {
    const hits = countHits("我的手机13800138000和密钥sk-abc123def456ghi");
    expect(hits.phone).toBe(1);
    expect(hits.key).toBe(1);
  });

  it("无敏感信息 has 0 hits", () => {
    const hits = countHits("你好，今天天气不错");
    expect(hits.phone).toBe(0);
    expect(hits.key).toBe(0);
  });
});

// --- C: Multi-rule Priority Snapshot ---

describe("C: multi-rule priority snapshot", () => {
  it("phone redacted before key in same text", () => {
    // Python applies PHONE_RE first, then KEY_RE
    const result = redactText("phone:13800138000,key:sk-abc123def456ghi");
    // Phone should be redacted first, then key
    expect(result).toBe("phone:[REDACTED_PHONE],key:[REDACTED_API_KEY]");
  });

  it("order matches Python for overlapping patterns", () => {
    // No overlapping possible between phone and key patterns, but verify both work
    const result = redactText("13800138000 sk-abc123def456ghi");
    expect(result).toBe("[REDACTED_PHONE] [REDACTED_API_KEY]");
  });
});

// --- D: No External Dependency Snapshot ---

describe("D: no external dependency snapshot", () => {
  it("source file imports are pure (no gateway/provider/model_router/prompt_guard/schemas)", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "redactor.ts"),
      "utf-8",
    );
    const forbidden = ["gateway", "provider_deepseek", "model_router", "prompt_guard", "schemas"];
    for (const dep of forbidden) {
      expect(source).not.toContain(dep);
    }
  });
});

// --- E: Redact Payload Snapshot ---

describe("E: redact payload snapshot", () => {
  it("payload str redacts", () => {
    const result = redactPayload("我的手机13800138000");
    expect(result).toBe("我的手机[REDACTED_PHONE]");
  });

  it("payload list redacts each string", () => {
    const result = redactPayload(["手机13800138000", "密钥sk-abc123"]);
    expect(result).toEqual(["手机[REDACTED_PHONE]", "密钥sk-abc123"]);
  });

  it("payload dict redacts string values", () => {
    const result = redactPayload({
      phone: "13800138000",
      key: "sk-abc123def456",
      name: "张三",
    }) as Record<string, unknown>;
    expect(result.phone).toBe("[REDACTED_PHONE]");
    expect(result.key).toBe("[REDACTED_API_KEY]");
    expect(result.name).toBe("张三");
  });

  it("payload nested dict redacts deeply", () => {
    const result = redactPayload({
      user: { phone: "13800138000", key: "sk-secret" },
      items: ["test", "sk-xyz789abc"],
    }) as Record<string, unknown>;
    expect((result.user as Record<string, unknown>).phone).toBe("[REDACTED_PHONE]");
    expect((result.items as unknown[])[1]).toBe("[REDACTED_API_KEY]");
  });

  it("payload int unchanged", () => {
    expect(redactPayload(12345)).toBe(12345);
  });

  it("payload null unchanged", () => {
    expect(redactPayload(null)).toBeNull();
  });

  it("payload empty list unchanged", () => {
    expect(redactPayload([])).toEqual([]);
  });

  it("payload empty dict unchanged", () => {
    expect(redactPayload({})).toEqual({});
  });
});

// --- F: Repeatable calls stable ---

describe("F: repeatable calls stable", () => {
  it("same redact_text inputs produce same output", () => {
    const a = redactText("我的手机13800138000和密钥sk-abc123def456ghi");
    const b = redactText("我的手机13800138000和密钥sk-abc123def456ghi");
    expect(a).toBe(b);
  });

  it("same redact_payload inputs produce same output", () => {
    const input = { phone: "13800138000", key: "sk-abc123def456" };
    const a = redactPayload(input);
    const b = redactPayload(input);
    expect(deepEqual(a, b)).toBe(true);
  });
});

// --- G: None/Null error behavior ---

describe("G: null/error behavior snapshot", () => {
  it("redactText null throws TypeError", () => {
    // @ts-expect-error testing runtime null
    expect(() => redactText(null)).toThrow(TypeError);
  });

  it("payload key preserves structure even with null values", () => {
    const result = redactPayload(["text", 42, { key: "sk-abc123" }, null]);
    expect(result).toEqual(["text", 42, { key: "sk-abc123" }, null]);
  });
});
