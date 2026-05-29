import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { explainRecommendation, generateRecommendation, createClassRecommendation } from "../ts-src/index.js";
import type { ClassRecommendation } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "recommendation_model.json");

interface FixtureCase {
  input: Record<string, unknown>;
  output: ClassRecommendation;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonExplainer(
  rec: ClassRecommendation,
  identityType: string = "parent",
): string {
  const tmpScript = resolve(tmpdir(), `parity_exp_${randomUUID()}.py`);
  const recJson = JSON.stringify(rec);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "recommendation-service", "src"))})`,
    "from recommendation_explainer import explain_recommendation",
    "from recommendation_model import ClassRecommendation",
    `rec_dict = json.loads(${JSON.stringify(recJson)})`,
    "rec = ClassRecommendation(**rec_dict)",
    `result = explain_recommendation(rec, ${JSON.stringify(identityType)})`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 10_000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return JSON.parse(output.trim()) as string;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

describe("recommendationExplainer parity tests", () => {
  it("matches Python output for all golden fixture recommendations (parent)", () => {
    for (const c of fixtures) {
      const tsOut = explainRecommendation(c.output, "parent");
      const pyOut = runPythonExplainer(c.output, "parent");
      expect(tsOut).toBe(pyOut);
    }
  });

  it("matches Python output for all golden fixture recommendations (student)", () => {
    for (const c of fixtures) {
      const tsOut = explainRecommendation(c.output, "student");
      const pyOut = runPythonExplainer(c.output, "student");
      expect(tsOut).toBe(pyOut);
    }
  });

  it("no-recommendation case: pronoun is baked into rec.next_questions by class_rules", () => {
    const rec = fixtures[0]!.output;
    expect(rec.next_questions[0]).toContain("孩子");
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("孩子是物理类还是历史类");
    // identity_type=student doesn't change next_questions (they're set in _no_recommendation)
    const resultStudent = explainRecommendation(rec, "student");
    expect(resultStudent).toContain("孩子是物理类还是历史类");
  });

  it("normal recommendation includes class type name", () => {
    const rec = fixtures[1]!.output;
    expect(rec.recommended_class_type).toBe("小班强化班");
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("小班强化班");
  });

  it("reasons section is included", () => {
    const rec = fixtures[1]!.output;
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("主要原因");
    for (const r of rec.reasons) {
      expect(result).toContain(r);
    }
  });

  it("not_suitable_if section is included when present", () => {
    const rec = fixtures[1]!.output;
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("不一定是最合适的");
    for (const ns of rec.not_suitable_if) {
      expect(result).toContain(ns);
    }
  });

  it("missing_info section is only included when also has next_questions", () => {
    const rec = fixtures[1]!.output;
    expect(rec.missing_info.length).toBeGreaterThan(0);
    expect(rec.next_questions.length).toBeGreaterThan(0);
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("还需要了解");
  });

  it("risk_warnings section is included when present", () => {
    const rec = fixtures[1]!.output;
    const result = explainRecommendation(rec, "parent");
    expect(result).toContain("温馨提示");
    for (const w of rec.risk_warnings) {
      expect(result).toContain(w);
    }
  });

  it("produces identical output for recommendation with empty missing_info", () => {
    const rec = createClassRecommendation({
      recommended_class_type: "冲刺班",
      confidence: "high",
      reasons: ["测试理由"],
      missing_info: [],
      next_questions: [],
    });
    const tsOut = explainRecommendation(rec, "parent");
    const pyOut = runPythonExplainer(rec, "parent");
    expect(tsOut).toBe(pyOut);
  });

  it("produces identical output for recommendation with empty next_questions", () => {
    const rec = createClassRecommendation({
      recommended_class_type: "冲刺班",
      confidence: "high",
      reasons: ["测试理由"],
      missing_info: ["subject_type"],
      next_questions: [],
    });
    const tsOut = explainRecommendation(rec, "parent");
    const pyOut = runPythonExplainer(rec, "parent");
    expect(tsOut).toBe(pyOut);
  });

  it("produces identical output for recommendation with only risk_warnings", () => {
    const rec = createClassRecommendation({
      recommended_class_type: "冲刺班",
      confidence: "high",
      reasons: [],
      not_suitable_if: [],
      missing_info: [],
      next_questions: [],
      risk_warnings: ["测试风险"],
    });
    const tsOut = explainRecommendation(rec, "parent");
    const pyOut = runPythonExplainer(rec, "parent");
    expect(tsOut).toBe(pyOut);
  });

  it("string formatting is byte-identical to Python output", () => {
    const rec = fixtures[2]!.output;
    const tsOut = explainRecommendation(rec, "parent");
    const pyOut = runPythonExplainer(rec, "parent");
    expect(tsOut.length).toBe(pyOut.length);
    for (let i = 0; i < tsOut.length; i++) {
      expect(tsOut.charCodeAt(i)).toBe(pyOut.charCodeAt(i));
    }
  });
});
