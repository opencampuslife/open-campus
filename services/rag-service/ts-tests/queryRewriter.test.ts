import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expandQuery, expandWithTags } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "query_rewriter.json");

interface FixtureOutput {
  ok: boolean;
  result?: string;
  error?: string;
  message?: string;
}

interface FixtureCase {
  desc: string;
  function: string;
  args: unknown[];
  output: FixtureOutput;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runTs(f: FixtureCase): FixtureOutput {
  try {
    const fn = f.function;
    const args = f.args;

    if (fn === "expand_query") {
      const query = args[0] as string;
      const intent = args.length > 1 ? (args[1] as string) : "faq";
      const result = expandQuery(query, intent);
      return { ok: true, result };
    }

    if (fn === "expand_with_tags") {
      const query = args[0] as string;
      const tags = args[1] as string[];
      const result = expandWithTags(query, tags);
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
  it("matches stored golden JSON output for all 30 fixtures", () => {
    for (const f of fixtures) {
      const tsResult = runTs(f);
      if (f.output.ok) {
        expect(tsResult.ok).toBe(true);
        expect(tsResult.result).toBe(f.output.result);
      } else {
        expect(tsResult.ok).toBe(false);
        expect(tsResult.error).toBe(f.output.error);
      }
    }
  });
});

// --- A: Rewrite Output Snapshot ---

describe("A: rewrite output snapshot", () => {
  it("expand_query 普通中文查询 matches Python", () => {
    const f = fixtures.find(x => x.desc === "普通中文查询" && x.function === "expand_query")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query 空字符串 matches Python", () => {
    const f = fixtures.find(x => x.desc === "空字符串")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query 仅空白字符串 matches Python", () => {
    const f = fixtures.find(x => x.desc === "仅空白字符串")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query very long query matches Python", () => {
    const f = fixtures.find(x => x.desc === "very long query")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query with intent=pricing_consulting matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_query explicit intent=pricing_consulting")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query with intent keywords already in query matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_query intent keywords already in query")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_query multiple synonym keywords matches Python", () => {
    const f = fixtures.find(x => x.desc === "multiple synonym keywords")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_with_tags basic matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_with_tags basic")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_with_tags empty query matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_with_tags empty query")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_with_tags empty tags matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_with_tags empty tags")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });

  it("expand_with_tags single tag matches Python", () => {
    const f = fixtures.find(x => x.desc === "expand_with_tags single tag")!;
    const ts = runTs(f);
    expect(ts.ok).toBe(true);
    expect(ts.result).toBe(f.output.result);
  });
});

// --- B: Edge Input Snapshot ---

describe("B: edge input snapshot", () => {
  it("空字符串 produces string starting with space", () => {
    const result = expandQuery("");
    // Python: " ".join([""] + intent_keywords_not_in_query) → " 说明 介绍 指南 常见问题 怎么样 如何"
    expect(result).toBe(" 说明 介绍 指南 常见问题 怎么样 如何");
  });

  it("仅空白字符串 preserves spaces in result", () => {
    const result = expandQuery("   ");
    expect(result).toBe("    说明 介绍 指南 常见问题 怎么样 如何");
  });

  it("query 含换行 preserves newline", () => {
    const result = expandQuery("学费\n多少");
    expect(result.includes("\n")).toBe(true);
  });

  it("query 含重复空格 preserves repeated spaces", () => {
    const result = expandQuery("学费    多少");
    expect(result).toBe("学费    多少 费用 收费 价格 多少钱 一年多少钱 说明 介绍 指南 常见问题 怎么样 如何");
  });

  it("query 含 emoji preserves emoji", () => {
    const result = expandQuery("学费多少😊");
    expect(result.includes("😊")).toBe(true);
  });

  it("query 含全角标点 preserves fullwidth punctuation", () => {
    const result = expandQuery("学费多少，多少钱啊！");
    expect(result).toBe("学费多少，多少钱啊！ 费用 收费 价格 一年多少钱 说明 介绍 指南 常见问题 怎么样 如何");
  });

  it("query 含标点 keeps question mark", () => {
    const result = expandQuery("学费多少?");
    expect(result.includes("?")).toBe(true);
  });

  it("None query throws TypeError", () => {
    // Python throws TypeError('argument of type NoneType is not iterable')
    // @ts-expect-error testing runtime null
    expect(() => expandQuery(null)).toThrow(TypeError);
  });

  it("None intent treated as default (no intent keywords added)", () => {
    // Python: None not in INTENT_KEYWORDS → no intent expansion
    // @ts-expect-error testing runtime null
    const result = expandQuery("学费", null);
    expect(result).toBe("学费 费用 收费 价格 多少钱 一年多少钱");
  });

  it("expand_with_tags None query throws TypeError", () => {
    // @ts-expect-error testing runtime null
    expect(() => expandWithTags(null, ["tag1"])).toThrow(TypeError);
  });

  it("expand_with_tags None tags throws TypeError", () => {
    // @ts-expect-error testing runtime null
    expect(() => expandWithTags("test", null)).toThrow(TypeError);
  });
});

// --- C: No External Dependency Snapshot ---

describe("C: no external dependency snapshot", () => {
  it("source file imports are pure (no retriever/search_router/LLM/filter/checker)", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "queryRewriter.ts"),
      "utf-8",
    );
    const forbidden = [
      "retriever", "search_router", "metadataFilter", "accessChecker",
    ];
    for (const dep of forbidden) {
      expect(source).not.toContain(dep);
    }
  });
});

// --- D: Repeatable calls stable ---

describe("D: repeatable calls stable", () => {
  it("same expand_query inputs produce same output", () => {
    const a = expandQuery("复读班价格多少");
    const b = expandQuery("复读班价格多少");
    expect(a).toBe(b);
  });

  it("same expand_with_tags inputs produce same output", () => {
    const a = expandWithTags("课程推荐", ["热门推荐", "限时优惠"]);
    const b = expandWithTags("课程推荐", ["热门推荐", "限时优惠"]);
    expect(a).toBe(b);
  });
});
