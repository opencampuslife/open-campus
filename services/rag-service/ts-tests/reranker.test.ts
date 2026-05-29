import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { rerank } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "reranker.json");

interface FixtureCase {
  desc: string;
  input: { scored: Record<string, unknown>[]; limit: number };
  output:
    | { ok: true; result: Record<string, unknown>[] }
    | { ok: false; error: string; message: string };
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a === "number" && typeof b === "number" && Number.isNaN(a) && Number.isNaN(b)) return true;
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

function runPythonRerank(
  scored: Record<string, unknown>[],
  limit: number,
): FixtureCase["output"] {
  const tmpScript = resolve(tmpdir(), `parity_rrk_${randomUUID()}.py`);
  const script = [
    "import json, re, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "rag-service", "src"))})`,
    "from reranker import rerank",
    `scored = json.loads(${JSON.stringify(JSON.stringify(scored))})`,
    `try:`,
    `  result = rerank(scored, ${JSON.stringify(limit)})`,
    `  raw = json.dumps({"ok": True, "result": result}, allow_nan=True)`,
    `  print(re.sub(r'\\bNaN\\b', 'null', raw))`,
    `except Exception as e:`,
    `  print(json.dumps({"ok": False, "error": type(e).__name__, "message": str(e)}))`,
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as FixtureCase["output"];
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

// --- Golden Fixture Parity (16 OK + 3 ERROR = 19 fixtures) ---

describe("reranker: golden fixture parity", () => {
  it("matches stored golden JSON output for all 19 fixtures", () => {
    for (const c of fixtures) {
      if (c.output.ok) {
        const tsResult = rerank(c.input.scored, c.input.limit);
        expect(deepEqual(tsResult, c.output.result)).toBe(true);
      } else {
        expect(() => rerank(c.input.scored, c.input.limit)).toThrow();
      }
    }
  });

  it("matches live Python output for all 19 fixtures", () => {
    for (const c of fixtures) {
      const tsOut = (() => {
        if (c.output.ok) {
          return { ok: true as const, result: rerank(c.input.scored, c.input.limit) };
        }
        try {
          rerank(c.input.scored, c.input.limit);
          return { ok: false as const, error: "NO_ERROR", message: "expected error" };
        } catch (e: unknown) {
          const err = e as Error;
          return { ok: false as const, error: err.name ?? err.constructor.name, message: err.message };
        }
      })();
      const pyOut = runPythonRerank(c.input.scored, c.input.limit);

      if (c.output.ok) {
        expect(tsOut.ok).toBe(true);
        expect(deepEqual((tsOut as { ok: true; result: Record<string, unknown>[] }).result, (pyOut as { ok: true; result: Record<string, unknown>[] }).result)).toBe(true);
      } else {
        expect(tsOut.ok).toBe(false);
        expect(pyOut.ok).toBe(false);
        const tsErr = tsOut as { ok: false; error: string; message: string };
        const pyErr = pyOut as { ok: false; error: string; message: string };
        expect(tsErr.error).toBe(pyErr.error);
      }
    }
  });
});

// --- A: Ranking Output Snapshot ---

describe("A: ranking output snapshot", () => {
  const normalInput = {
    scored: [
      { id: "a", title: "Doc A", score: 0.95 },
      { id: "b", title: "Doc B", score: 0.80 },
      { id: "c", title: "Doc C", score: 0.99 },
      { id: "d", title: "Doc D", score: 0.70 },
    ],
    limit: 5,
  };

  it("sorts descending by score", () => {
    const result = rerank(normalInput.scored, normalInput.limit);
    expect(result[0]!.id).toBe("c");
    expect(result[1]!.id).toBe("a");
    expect(result[2]!.id).toBe("b");
    expect(result[3]!.id).toBe("d");
  });

  it("preserves all fields including unknown", () => {
    const items = [
      { id: "a", score: 0.5, snippet: "Hello", extra_field: "keep_me" },
      { id: "b", score: 0.8, snippet: "World", meta: { key: "val" } },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("b");
    expect(result[0]!.extra_field).toBeUndefined();
    expect(result[1]!.id).toBe("a");
    expect(result[1]!.extra_field).toBe("keep_me");
  });

  it("chinese text sorts correctly by score", () => {
    const items = [
      { id: "a", title: "数学基础", snippet: "包含代数与几何", score: 0.9 },
      { id: "b", title: "英语阅读", snippet: "阅读理解技巧", score: 0.85 },
      { id: "c", title: "语文作文", snippet: "写作方法指导", score: 0.95 },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("c");
    expect(result[1]!.id).toBe("a");
    expect(result[2]!.id).toBe("b");
  });

  it("matches Python output for normal sort", () => {
    const tsResult = rerank(normalInput.scored, normalInput.limit);
    const pyResult = runPythonRerank(normalInput.scored, normalInput.limit);
    expect(pyResult.ok).toBe(true);
    expect(deepEqual(tsResult, (pyResult as { ok: true; result: Record<string, unknown>[] }).result)).toBe(true);
  });
});

// --- B: Tie-break Snapshot ---

describe("B: tie-break snapshot", () => {
  it("same score preserves input order", () => {
    const items = [
      { id: "z", score: 0.7 },
      { id: "y", score: 0.7 },
      { id: "x", score: 0.7 },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("z");
    expect(result[1]!.id).toBe("y");
    expect(result[2]!.id).toBe("x");
  });

  it("tie-break matches Python stable sort order", () => {
    const items = [
      { id: "a", score: 0.8, title: "Alpha" },
      { id: "b", score: 0.8, title: "Beta" },
      { id: "c", score: 0.8, title: "Gamma" },
    ];
    const tsResult = rerank(items, 5);
    const pyResult = runPythonRerank(items, 5);
    expect(pyResult.ok).toBe(true);
    expect(deepEqual(tsResult, (pyResult as { ok: true; result: Record<string, unknown>[] }).result)).toBe(true);
    expect(tsResult[0]!.title).toBe("Alpha");
    expect(tsResult[1]!.title).toBe("Beta");
    expect(tsResult[2]!.title).toBe("Gamma");
  });
});

// --- C: Score Edge Behavior Snapshot ---

describe("C: score edge behavior snapshot", () => {
  it("score zero sorts correctly", () => {
    const items = [
      { id: "a", score: 0.5 },
      { id: "b", score: 0.0 },
      { id: "c", score: 0.3 },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("a");
    expect(result[1]!.id).toBe("c");
    expect(result[2]!.id).toBe("b");
  });

  it("score negative sorts correctly", () => {
    const items = [
      { id: "a", score: 0.5 },
      { id: "b", score: -1.0 },
      { id: "c", score: 0.0 },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("a");
    expect(result[1]!.id).toBe("c");
    expect(result[2]!.id).toBe("b");
  });

  it("score string sorts lexically", () => {
    const items = [
      { id: "a", score: "0.8" },
      { id: "b", score: "0.5" },
      { id: "c", score: "0.95" },
    ];
    const result = rerank(items, 5);
    // Lexical: "0.95" > "0.8" because '9' > '8' at position 2
    expect(result[0]!.id).toBe("c");
    expect(result[1]!.id).toBe("a");
    expect(result[2]!.id).toBe("b");
  });

  it("score string matches Python lexical sort", () => {
    const items = [
      { id: "a", score: "0.8" },
      { id: "b", score: "0.5" },
      { id: "c", score: "0.95" },
    ];
    const tsResult = rerank(items, 5);
    const pyResult = runPythonRerank(items, 5);
    expect(pyResult.ok).toBe(true);
    expect(deepEqual(tsResult, (pyResult as { ok: true; result: Record<string, unknown>[] }).result)).toBe(true);
  });

  it("score null throws TypeError", () => {
    const items = [
      { id: "a", score: 0.5 },
      { id: "b", score: null },
    ];
    expect(() => rerank(items, 5)).toThrow(TypeError);
  });

  it("score missing throws KeyError-like error", () => {
    const items = [
      { id: "a", score: 0.5 },
      { id: "b", title: "No Score" },
    ];
    expect(() => rerank(items, 5)).toThrow(Error);
  });

  it("mixed types string+number throws TypeError", () => {
    const items = [
      { id: "a", score: "0.8" },
      { id: "b", score: 0.5 },
    ];
    expect(() => rerank(items, 5)).toThrow(TypeError);
  });

  it("NaN score stays in input position (Python Timsort behavior)", () => {
    // Python: NaN comparisons always return False → Timsort preserves input order
    const items = [
      { id: "a", score: 0.5 },
      { id: "b", score: NaN },
      { id: "c", score: 0.3 },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("a");
    expect(result[1]!.id).toBe("b");
    expect(Number.isNaN(result[1]!.score as number)).toBe(true);
    expect(result[2]!.id).toBe("c");
  });

  it("NaN score matches Python order (via direct Python NaN construction)", () => {
    // JSON.stringify converts NaN → null, so we must construct NaN in Python directly
    const tmpScript = resolve(tmpdir(), `parity_nan_${randomUUID()}.py`);
    const script = [
      "import json, sys",
      `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "rag-service", "src"))})`,
      "from reranker import rerank",
      "scored = [{'id': 'a', 'score': 0.5}, {'id': 'b', 'score': float('nan')}, {'id': 'c', 'score': 0.3}]",
      "result = rerank(scored, 5)",
      "out = []",
      "for item in result:",
      "  out.append({'id': item['id'], 'score_is_nan': __import__('math').isnan(item['score'])})",
      "print(json.dumps(out))",
    ].join("\n");
    writeFileSync(tmpScript, script, "utf-8");
    let pyOutput: string;
    try {
      pyOutput = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
        cwd: REPO_ROOT, encoding: "utf-8", timeout: 15_000,
      }).trim();
    } finally {
      try { unlinkSync(tmpScript); } catch { /* ignore */ }
    }
    const pyData = JSON.parse(pyOutput) as Array<{ id: string; score_is_nan: boolean }>;

    // TS order
    const tsResult = rerank([
      { id: "a", score: 0.5 },
      { id: "b", score: NaN },
      { id: "c", score: 0.3 },
    ], 5);
    expect(tsResult[0]!.id).toBe("a");
    expect(tsResult[1]!.id).toBe("b");
    expect(Number.isNaN(tsResult[1]!.score as number)).toBe(true);
    expect(tsResult[2]!.id).toBe("c");

    // Python should agree on order and NaN position
    expect(pyData[0]!.id).toBe("a");
    expect(pyData[1]!.id).toBe("b");
    expect(pyData[1]!.score_is_nan).toBe(true);
    expect(pyData[2]!.id).toBe("c");
  });

  it("all NaN scores preserve input order", () => {
    const items = [
      { id: "a", score: NaN },
      { id: "b", score: NaN },
    ];
    const result = rerank(items, 5);
    expect(result[0]!.id).toBe("a");
    expect(result[1]!.id).toBe("b");
  });

  it("empty array returns empty", () => {
    const result = rerank([], 5);
    expect(result).toEqual([]);
  });

  it("single element returns single", () => {
    const result = rerank([{ id: "a", score: 0.5 }], 5);
    expect(result.length).toBe(1);
    expect(result[0]!.id).toBe("a");
  });

  it("limit truncation returns at most limit items", () => {
    const items = [
      { id: "a", score: 0.9 },
      { id: "b", score: 0.8 },
      { id: "c", score: 0.7 },
      { id: "d", score: 0.6 },
      { id: "e", score: 0.5 },
      { id: "f", score: 0.4 },
    ];
    const result = rerank(items, 3);
    expect(result.length).toBe(3);
    expect(result[0]!.id).toBe("a");
    expect(result[1]!.id).toBe("b");
    expect(result[2]!.id).toBe("c");
  });

  it("limit larger than array returns all", () => {
    const items = [
      { id: "a", score: 0.9 },
      { id: "b", score: 0.8 },
    ];
    const result = rerank(items, 10);
    expect(result.length).toBe(2);
  });

  it("limit zero returns empty", () => {
    const items = [
      { id: "a", score: 0.9 },
      { id: "b", score: 0.8 },
    ];
    const result = rerank(items, 0);
    expect(result).toEqual([]);
  });
});

// --- D: Repeatable calls stable ---

describe("D: repeatable calls stable", () => {
  it("same inputs produce same outputs", () => {
    const items = [
      { id: "a", score: 0.7 },
      { id: "b", score: 0.9 },
      { id: "c", score: 0.5 },
    ];
    const a = rerank(items, 5);
    const b = rerank(items, 5);
    expect(deepEqual(a, b)).toBe(true);
  });

  it("input array not mutated", () => {
    const items = [
      { id: "a", score: 0.7 },
      { id: "b", score: 0.9 },
    ];
    const original = [...items];
    rerank(items, 5);
    expect(items).toEqual(original);
  });
});
