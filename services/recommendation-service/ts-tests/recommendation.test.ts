import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { generateRecommendation, recommend } from "../ts-src/index.js";
import type { ClassRecommendation } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "recommendation_model.json");

interface FixtureCase {
  input: {
    profile: Record<string, unknown>;
    allowed_evidence: Record<string, unknown>[];
    campus?: string | null;
    role?: string;
    consultation_stage?: string;
  };
  output: ClassRecommendation;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonRecommendation(input: FixtureCase["input"]): ClassRecommendation {
  const tmpScript = resolve(tmpdir(), `parity_rec_${randomUUID()}.py`);
  const inputJson = JSON.stringify(input);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "recommendation-service", "src"))})`,
    "from recommendation_engine import generate_recommendation",
    `inp = json.loads(${JSON.stringify(inputJson)})`,
    `result = generate_recommendation(**inp)`,
    "print(json.dumps({k: v for k, v in result.__dict__.items() if not k.startswith('_')}, ensure_ascii=False, default=str))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 10_000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return JSON.parse(output.trim()) as ClassRecommendation;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

describe("recommendation engine parity tests", () => {
  it("has 6 golden fixture cases", () => {
    expect(fixtures.length).toBe(6);
  });

  it("matches golden baseline for all fixtures", () => {
    for (const c of fixtures) {
      const tsOutput = generateRecommendation(
        c.input.profile,
        c.input.allowed_evidence,
        c.input.campus ?? null,
        c.input.role ?? "parent",
        c.input.consultation_stage ?? "NEEDS_ASSESSMENT",
      );
      expect(tsOutput).toEqual(c.output);
    }
  });

  it("produces identical output to Python for all fixtures", () => {
    for (const c of fixtures) {
      const tsOutput = generateRecommendation(
        c.input.profile,
        c.input.allowed_evidence,
        c.input.campus ?? null,
        c.input.role ?? "parent",
        c.input.consultation_stage ?? "NEEDS_ASSESSMENT",
      );
      const pyOutput = runPythonRecommendation(c.input);
      expect(tsOutput).toEqual(pyOutput);
    }
  });

  it("applies defaults when role is omitted", () => {
    const result = generateRecommendation({ current_score: 400 }, []);
    expect(result.confidence).toBe("low");
    expect(result.missing_info).toContain("subject_type");
  });

  it("applies defaults when campus is omitted", () => {
    const result = generateRecommendation(
      { current_score: 400, weak_subjects: ["math", "physics"], self_discipline_level: "medium" },
      [],
    );
    expect(result.recommended_class_type).toBe("小班强化班");
  });

  it("returns fallback for insufficient profile", () => {
    const result = generateRecommendation({}, []);
    expect(result.recommended_class_type).toBeNull();
    expect(result.confidence).toBe("low");
    expect(result.reasons).toContain("当前画像信息不足以做出班型推荐");
  });

  it("detects missing profile fields in engine", () => {
    const result = generateRecommendation({ current_score: 250 }, []);
    expect(result.missing_info).toContain("subject_type");
  });

  it("handles non-ASCII profile values", () => {
    const result = generateRecommendation(
      { current_score: 400, weak_subjects: ["数学", "英语"], self_discipline_level: "medium" },
      [{ chunk_id: "zh1", content: "小班强化课程 数学" }],
    );
    expect(result.recommended_class_type).toBe("小班强化班");
    expect(result.evidence_ids).toContain("zh1");
  });

  it("class_rules.recommend works standalone", () => {
    const result = recommend(
      { current_score: 400, weak_subjects: ["math", "physics"], self_discipline_level: "medium" },
      [],
    );
    expect(result.recommended_class_type).toBe("小班强化班");
  });

  it("class_rules returns noRecommendation when no rules match", () => {
    const result = recommend({ current_score: 200 }, []);
    expect(result.recommended_class_type).toBeNull();
    expect(result.confidence).toBe("low");
  });
});
