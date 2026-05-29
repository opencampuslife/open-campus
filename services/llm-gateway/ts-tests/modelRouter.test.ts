import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { routeModel } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "model_router.json");

interface FixtureOutput {
  ok: boolean;
  result?: Record<string, string | null>;
  error?: string;
  message?: string;
}

interface FixtureCase {
  function: string;
  desc: string;
  input: { task: string; scope: Record<string, unknown> };
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

// Reset env var before each test
beforeEach(() => {
  delete process.env.DEEPSEEK_MODEL;
});

// --- Golden Fixture Parity ---

describe("golden fixture parity", () => {
  it("matches stored golden JSON for all fixtures (with default env)", () => {
    for (const f of fixtures) {
      if (f.desc === "custom model env var") continue;
      if (f.desc === "missing env var uses default") continue;
      const input = f.input;
      const tsResult = routeModel(input.task, input.scope);
      if (f.output.ok) {
        expect(deepEqual(tsResult, f.output.result)).toBe(true);
      } else {
        // Not expecting errors for route_model currently
        expect(f.output.ok).toBe(true);
      }
    }
  });

  it("custom env var matches golden fixture", () => {
    const f = fixtures.find(x => x.desc === "custom model env var")!;
    process.env.DEEPSEEK_MODEL = "custom-model-v1";
    const result = routeModel(f.input.task, f.input.scope);
    expect(deepEqual(result, f.output.result)).toBe(true);
  });

  it("missing env var uses default", () => {
    const f = fixtures.find(x => x.desc === "missing env var uses default")!;
    delete process.env.DEEPSEEK_MODEL;
    const result = routeModel(f.input.task, f.input.scope);
    expect(deepEqual(result, f.output.result)).toBe(true);
  });
});

// --- A: Route Output Snapshot ---

describe("A: route output snapshot", () => {
  it("returns correct provider and model", () => {
    const result = routeModel("admissions_answer", { role: "visitor" });
    expect(result.provider).toBe("deepseek");
    expect(result.model).toBe("deepseek-v4-flash");
  });

  it("returns task as provided", () => {
    const result = routeModel("custom_task", { role: "visitor" });
    expect(result.task).toBe("custom_task");
  });

  it("returns role from scope", () => {
    const result = routeModel("test", { role: "parent" });
    expect(result.role).toBe("parent");
  });

  it("empty scope defaults role to unknown", () => {
    const result = routeModel("test", {});
    expect(result.role).toBe("unknown");
  });

  it("null role preserved (not defaulted)", () => {
    const result = routeModel("test", { role: null });
    expect(result.role).toBeNull();
  });

  it("scope with extra fields returns only expected keys", () => {
    const result = routeModel("test", { role: "visitor", campus: "bj", extra: true });
    expect(Object.keys(result).sort()).toEqual(["model", "provider", "role", "task"]);
  });
});

// --- B: Repeatable calls stable ---

describe("B: repeatable calls stable", () => {
  it("same inputs produce same output", () => {
    const scope = { role: "visitor", campus: "all" };
    const a = routeModel("admissions_answer", scope);
    const b = routeModel("admissions_answer", scope);
    expect(deepEqual(a, b)).toBe(true);
  });
});
