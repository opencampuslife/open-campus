import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { evaluateAnswer, rewriteAnswer, evaluateAndRewrite } from "../ts-src/index.js";
import type { ComplianceResult } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "compliance_checker.json");

interface FixtureCase {
  input: { answer: string; scope: Record<string, string> };
  output: ComplianceResult;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonEvaluate(
  answer: string,
  scope: Record<string, unknown>,
): ComplianceResult {
  const tmpScript = resolve(tmpdir(), `checker_eval_${randomUUID()}.py`);
  const script = [
    "import json, sys, pathlib",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "compliance-service", "src"))})`,
    "from checker import evaluate_answer",
    `result = evaluate_answer(${JSON.stringify(answer)}, ${JSON.stringify(scope)}, pathlib.Path(${JSON.stringify(REPO_ROOT)}))`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as ComplianceResult;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

function runPythonRewrite(
  answer: string,
  violations: string[],
): string {
  const tmpScript = resolve(tmpdir(), `checker_write_${randomUUID()}.py`);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "compliance-service", "src"))})`,
    "from checker import rewrite_answer",
    `result = rewrite_answer(${JSON.stringify(answer)}, ${JSON.stringify(violations)})`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as string;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (typeof a !== "object" || typeof b !== "object") return false;
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

// --- Golden Fixture Parity ---

describe("compliance checker: golden fixture parity", () => {
  it("matches stored golden JSON output for all 10 fixtures", () => {
    for (const c of fixtures) {
      const tsOut = evaluateAnswer(c.input.answer, c.input.scope, REPO_ROOT);
      expect(deepEqual(tsOut, c.output)).toBe(true);
    }
  });

  it("matches live Python output for all 10 fixtures", () => {
    for (const c of fixtures) {
      const tsOut = evaluateAnswer(c.input.answer, c.input.scope, REPO_ROOT);
      const pyOut = runPythonEvaluate(c.input.answer, c.input.scope);
      expect(deepEqual(tsOut, pyOut)).toBe(true);
    }
  });

  it("produces identical violations array order for multi-violation case (fixture #6)", () => {
    const input = fixtures[5]!.input;
    const tsOut = evaluateAnswer(input.answer, input.scope, REPO_ROOT);
    const pyOut = runPythonEvaluate(input.answer, input.scope);
    expect(tsOut.violations).toEqual(pyOut.violations);
  });
});

// --- Rule-Level Snapshot Tests ---

describe("compliance checker: rule-level snapshots", () => {
  it("blocked phrase: 保证录取", () => {
    const result = evaluateAnswer("我们保证录取，请放心。", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(false);
    expect(result.violations).toContain("保证录取");
    expect(result.rewrite_guidance[0]).toContain("non-promissory");
  });

  it("blocked phrase: 保证提分", () => {
    const result = evaluateAnswer("保证提分，不过退款。", { role: "student" }, REPO_ROOT);
    expect(result.passed).toBe(false);
    expect(result.violations).toContain("保证提分");
    expect(result.rewrite_guidance[0]).toContain("non-promissory");
  });

  it("blocked phrase: 肯定能上本科", () => {
    const result = evaluateAnswer("你肯定能上本科。", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(false);
    expect(result.violations).toContain("肯定能上本科");
  });

  it("blocked phrase: 一定能冲一本", () => {
    const result = evaluateAnswer("一定能冲一本！", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(false);
    expect(result.violations).toContain("一定能冲一本");
  });

  it("blocked phrase: 内部名额 (only external roles)", () => {
    const visitorResult = evaluateAnswer("有内部名额。", { role: "visitor" }, REPO_ROOT);
    expect(visitorResult.violations).toContain("内部名额");
    const salesResult = evaluateAnswer("有内部名额。", { role: "sales" }, REPO_ROOT);
    expect(salesResult.passed).toBe(true);
  });

  it("blocked phrase: 优惠底价 (only external roles)", () => {
    const studentResult = evaluateAnswer("优惠底价5000。", { role: "student" }, REPO_ROOT);
    expect(studentResult.violations).toContain("优惠底价");
    const adminResult = evaluateAnswer("优惠底价5000。", { role: "admin" }, REPO_ROOT);
    expect(adminResult.passed).toBe(true);
  });

  it("internal reference leak: 内部参考", () => {
    const result = evaluateAnswer("这是内部参考的文件。", { role: "student" }, REPO_ROOT);
    expect(result.violations).toContain("internal_reference_leak");
  });

  it("internal reference leak: 内部规则", () => {
    const result = evaluateAnswer("按内部规则处理。", { role: "parent" }, REPO_ROOT);
    expect(result.violations).toContain("internal_reference_leak");
  });

  it("internal reference leak: 内部话术", () => {
    const result = evaluateAnswer("用内部话术回答。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("internal_reference_leak");
  });

  it("internal reference leak: 内部优惠", () => {
    const result = evaluateAnswer("内部优惠不对外。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("internal_reference_leak");
  });

  it("internal reference leak NOT triggered for non-external role", () => {
    const result = evaluateAnswer("这是内部参考的文件。", { role: "sales" }, REPO_ROOT);
    expect(result.violations).not.toContain("internal_reference_leak");
    expect(result.passed).toBe(true);
  });

  it("privacy phone number: 1[3-9]XXXXXXXXX pattern", () => {
    const result = evaluateAnswer("联系我：13800138000。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("privacy_phone_number");
  });

  it("privacy phone number: not triggered for short digits", () => {
    const result = evaluateAnswer("号码138。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).not.toContain("privacy_phone_number");
  });

  it("absolute claim: 100%", () => {
    const result = evaluateAnswer("100%保证提分。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("absolute_claim");
  });

  it("absolute claim: 一定会", () => {
    const result = evaluateAnswer("你一定会成功。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("absolute_claim");
  });

  it("absolute claim NOT triggered without keywords", () => {
    const result = evaluateAnswer("希望你成功。", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).not.toContain("absolute_claim");
  });
});

// --- Multi-Rule & Ordering ---

describe("compliance checker: multi-rule and ordering", () => {
  it("multiple rules hit in correct order: blocked_phrases > leak > phone > absolute", () => {
    const result = evaluateAnswer(
      "保证录取，内部规则是100%成功。联系13900001111。",
      { role: "visitor" },
      REPO_ROOT,
    );
    expect(result.violations).toEqual([
      "保证录取",
      "internal_reference_leak",
      "privacy_phone_number",
      "absolute_claim",
    ]);
  });

  it("multiple blocked phrases produce multiple violations in yaml order", () => {
    const result = evaluateAnswer(
      "保证录取，肯定能上本科，一定能冲一本。",
      { role: "visitor" },
      REPO_ROOT,
    );
    expect(result.violations).toContain("保证录取");
    expect(result.violations).toContain("肯定能上本科");
    expect(result.violations).toContain("一定能冲一本");
    // Order should follow YAML blocked_phrases definition order
    expect(result.violations.indexOf("保证录取")).toBeLessThan(
      result.violations.indexOf("肯定能上本科"),
    );
    expect(result.violations.indexOf("肯定能上本科")).toBeLessThan(
      result.violations.indexOf("一定能冲一本"),
    );
  });

  it("duplicate same blocked phrase only produces one violation", () => {
    // Python only appends once because duplicate check happens on iteration
    const result = evaluateAnswer(
      "保证录取，保证录取。",
      { role: "visitor" },
      REPO_ROOT,
    );
    expect(result.violations.filter((v) => v === "保证录取").length).toBe(1);
  });

  it("violations order stability across same inputs", () => {
    const a = evaluateAnswer("保证录取，内部规则，100%。联系13800138000。", { role: "visitor" }, REPO_ROOT);
    const b = evaluateAnswer("保证录取，内部规则，100%。联系13800138000。", { role: "visitor" }, REPO_ROOT);
    expect(a.violations).toEqual(b.violations);
  });
});

// --- Rewrite Guidance Exact Snapshot ---

describe("compliance checker: rewrite guidance byte-level", () => {
  it("promise_risk guidance for blocked phrase 保证录取", () => {
    const result = evaluateAnswer("保证录取。", { role: "visitor" }, REPO_ROOT);
    expect(result.rewrite_guidance.length).toBe(1);
    expect(result.rewrite_guidance[0]).toBe(
      "Use non-promissory language. Explain that outcomes depend on baseline, execution, weak subjects, and learning period.",
    );
  });

  it("promise_risk guidance for absolute_claim", () => {
    const result = evaluateAnswer("100%保证。", { role: "visitor" }, REPO_ROOT);
    expect(result.rewrite_guidance.length).toBe(1);
    expect(result.rewrite_guidance[0]).toBe(
      "Use non-promissory language. Explain that outcomes depend on baseline, execution, weak subjects, and learning period.",
    );
  });

  it("pricing_risk guidance for 优惠底价", () => {
    const result = evaluateAnswer("优惠底价5000。", { role: "student" }, REPO_ROOT);
    expect(result.rewrite_guidance.length).toBe(1);
    expect(result.rewrite_guidance[0]).toBe(
      "Provide public pricing range or invite verified consultation. Do not reveal internal discount approval rules.",
    );
  });

  it("pricing_risk guidance for internal_reference_leak", () => {
    const result = evaluateAnswer("内部规则。", { role: "visitor" }, REPO_ROOT);
    expect(result.rewrite_guidance.length).toBe(1);
    expect(result.rewrite_guidance[0]).toBe(
      "Provide public pricing range or invite verified consultation. Do not reveal internal discount approval rules.",
    );
  });

  it("privacy_risk guidance for phone number", () => {
    const result = evaluateAnswer("电话13900001111。", { role: "visitor" }, REPO_ROOT);
    expect(result.rewrite_guidance.length).toBe(1);
    expect(result.rewrite_guidance[0]).toBe(
      "Redact names, phone numbers, scores, and identifiable student cases unless the user is authorized.",
    );
  });

  it("multi-violation guidance in correct order: promise > pricing > privacy", () => {
    const result = evaluateAnswer(
      "保证录取，内部规则，100%。联系13800138000。",
      { role: "visitor" },
      REPO_ROOT,
    );
    expect(result.rewrite_guidance.length).toBe(3);
    expect(result.rewrite_guidance[0]).toContain("non-promissory");
    expect(result.rewrite_guidance[1]).toContain("pricing range");
    expect(result.rewrite_guidance[2]).toContain("Redact");
  });

  it("guidance byte-level matches Python exactly", () => {
    const result = evaluateAnswer(
      "保证录取，内部规则，100%。联系13800138000。",
      { role: "parent" },
      REPO_ROOT,
    );
    const pyResult = runPythonEvaluate(
      "保证录取，内部规则，100%。联系13800138000。",
      { role: "parent" },
    );
    expect(result.rewrite_guidance.length).toBe(pyResult.rewrite_guidance.length);
    for (let i = 0; i < result.rewrite_guidance.length; i++) {
      expect(result.rewrite_guidance[i]!.length).toBe(pyResult.rewrite_guidance[i]!.length);
      expect(result.rewrite_guidance[i]).toBe(pyResult.rewrite_guidance[i]);
    }
  });
});

// --- rewrite_answer ---

describe("rewriteAnswer function parity", () => {
  it("privacy phone number gets privacy rewrite", () => {
    const rewritten = rewriteAnswer("联系13800138000。", ["privacy_phone_number"]);
    expect(rewritten).toContain("个人隐私信息");
    expect(rewritten).toContain("授权场景");
  });

  it("internal_reference_leak gets pricing rewrite", () => {
    const rewritten = rewriteAnswer("内部规则。", ["internal_reference_leak"]);
    expect(rewritten).toContain("正式口径");
    expect(rewritten).toContain("未公开的优惠");
  });

  it("优惠底价 gets same rewrite as internal_reference_leak", () => {
    const leakWritten = rewriteAnswer("内部规则。", ["internal_reference_leak"]);
    const priceWritten = rewriteAnswer("优惠底价5000。", ["优惠底价"]);
    expect(leakWritten).toBe(priceWritten);
  });

  it("absolute_claim gets generic rewrite", () => {
    const rewritten = rewriteAnswer("100%保证。", ["absolute_claim"]);
    expect(rewritten).toContain("承诺固定提分、保证录取");
  });

  it("保证录取 gets generic rewrite (not matched by specific branches)", () => {
    const rewritten = rewriteAnswer("保证录取。", ["保证录取"]);
    expect(rewritten).toContain("承诺固定提分、保证录取");
  });

  it("matches Python rewrite output", () => {
    const tsOut = rewriteAnswer("联系13800138000。", ["privacy_phone_number"]);
    const pyOut = runPythonRewrite("联系13800138000。", ["privacy_phone_number"]);
    expect(tsOut).toBe(pyOut);
  });
});

// --- evaluateAndRewrite integration ---

describe("evaluateAndRewrite integration", () => {
  it("passed=true returns original answer as rewritten_answer", () => {
    const result = evaluateAndRewrite("正常文本。", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(true);
    expect(result.rewritten_answer).toBe("正常文本。");
  });

  it("passed=false returns rewritten answer", () => {
    const result = evaluateAndRewrite("联系13800138000。", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(false);
    expect(result.rewritten_answer).toContain("个人隐私信息");
    expect(result.rewritten_answer).not.toContain("13800138000");
  });
});

// --- Edge Cases ---

describe("compliance checker: edge cases", () => {
  it("empty string passes", () => {
    const result = evaluateAnswer("", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(true);
    expect(result.violations).toEqual([]);
    expect(result.rewrite_guidance).toEqual([]);
  });

  it("whitespace-only string passes", () => {
    const result = evaluateAnswer("   ", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(true);
    expect(result.violations).toEqual([]);
  });

  it("non-Chinese text with no keywords passes", () => {
    const result = evaluateAnswer("Hello, this is a normal message.", { role: "visitor" }, REPO_ROOT);
    expect(result.passed).toBe(true);
  });

  it("Chinese-English mixed with blocked phrase", () => {
    const result = evaluateAnswer("This course 保证录取 for sure.", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).toContain("保证录取");
  });

  it("full-width symbols don't affect keyword detection", () => {
    const result = evaluateAnswer("保证录取！100％成功。", { role: "visitor" }, REPO_ROOT);
    // Python checks "100%" (half-width percent), full-width ％ doesn't match
    expect(result.violations).toContain("保证录取");
    expect(result.violations).not.toContain("absolute_claim");
  });

  it("zero-width characters don't interfere with matching", () => {
    const result = evaluateAnswer("保证\u200B录取", { role: "visitor" }, REPO_ROOT);
    // zero-width space breaks the match: 保证\u200B录取 is not 保证录取
    expect(result.violations).not.toContain("保证录取");
    expect(result.passed).toBe(true);
  });

  it("partial substring doesn't match longer phrase", () => {
    const result = evaluateAnswer("保证", { role: "visitor" }, REPO_ROOT);
    expect(result.violations).not.toContain("保证录取");
    expect(result.passed).toBe(true);
  });

  it("phone-like number embedded in longer text works", () => {
    const result = evaluateAnswer("编号13912345678X", { role: "visitor" }, REPO_ROOT);
    // Python PHONE_PATTERN.search checks if pattern exists anywhere
    expect(result.violations).toContain("privacy_phone_number");
  });
});

// --- YAML contents snapshot ---

describe("YAML config snapshot", () => {
  it("blocked_phrases order matches YAML definition", () => {
    const result1 = evaluateAnswer("保证录取肯定能上本科一定能冲一本内部名额优惠底价保证提分", { role: "visitor" }, REPO_ROOT);
    const blockedHits = result1.violations.filter((v) =>
      ["保证录取", "保证提分", "肯定能上本科", "一定能冲一本", "内部名额", "优惠底价"].includes(v),
    );
    expect(blockedHits).toEqual([
      "保证录取",
      "保证提分",
      "肯定能上本科",
      "一定能冲一本",
      "内部名额",
      "优惠底价",
    ]);
  });

  it("rewrite_guidance key order matches YAML", () => {
    const result = evaluateAnswer(
      "保证录取，内部规则，100%。联系13800138000。",
      { role: "visitor" },
      REPO_ROOT,
    );
    expect(result.rewrite_guidance.length).toBe(3);
    expect(result.rewrite_guidance[0]).toContain("non-promissory");
    expect(result.rewrite_guidance[1]).toContain("pricing range");
    expect(result.rewrite_guidance[2]).toContain("Redact");
  });
});
