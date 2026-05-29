import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  EvidenceChunkSchema,
  evidenceChunkFromChunk,
  LLMRequestSchema,
  llmRequestToPolicyDict,
} from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "llm_gateway_schemas.json");

interface FixtureOutput {
  ok: boolean;
  result?: Record<string, unknown>;
  error?: string;
  message?: string;
}

interface FixtureCase {
  desc: string;
  group: string;
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

// --- Helper: run TS implementation for a fixture case ---

function runTs(f: FixtureCase): FixtureOutput {
  try {
    const group = f.group;
    const input = f.input as Record<string, unknown>;

    if (group === "evidence_chunk") {
      const desc = f.desc;
      if (desc.includes("from_chunk")) {
        const chunk = input.chunk as Record<string, unknown>;
        const result = evidenceChunkFromChunk(chunk);
        return { ok: true, result: result as unknown as Record<string, unknown> };
      }
      if (desc.includes("to_prompt_dict")) {
        const kwargs = input.kwargs as Record<string, unknown>;
        const result = EvidenceChunkSchema.parse(kwargs);
        return { ok: true, result: result as unknown as Record<string, unknown> };
      }
      // direct construction
      const kwargs = input.kwargs as Record<string, unknown>;
      const result = EvidenceChunkSchema.parse(kwargs);
      return { ok: true, result: result as unknown as Record<string, unknown> };
    }

    if (group === "llm_request") {
      const desc = f.desc;
      if (desc.includes("to_policy_dict")) {
        const kwargs = input.kwargs as Record<string, unknown>;
        const parsed = LLMRequestSchema.parse(kwargs);
        const result = llmRequestToPolicyDict(parsed);
        return { ok: true, result: result as Record<string, unknown> };
      }
      // direct construction
      const kwargs = input.kwargs as Record<string, unknown>;
      const result = LLMRequestSchema.parse(kwargs);
      return { ok: true, result: result as unknown as Record<string, unknown> };
    }

    return { ok: false, error: "UnknownGroup", message: `Unknown group: ${group}` };
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
  it("matches stored golden JSON output for all 15 fixtures", () => {
    for (const f of fixtures) {
      const tsResult = runTs(f);
      if (f.output.ok) {
        expect(tsResult.ok).toBe(true);
        expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
      } else {
        expect(tsResult.ok).toBe(false);
      }
    }
  });
});

// --- A: Schema Output Snapshot ---

describe("A: schema output snapshot", () => {
  it("EvidenceChunk full construction matches Python", () => {
    const f = fixtures[0]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("from_chunk full matches Python", () => {
    const f = fixtures[1]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("LLMRequest minimal has correct fields", () => {
    const f = fixtures[7]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    const r = tsResult.result!;
    // Defaults should match Python
    expect(r.answer_policy).toEqual({});
    expect(r.output_format).toBe("plain_text_with_sources");
    expect(r.risk_level).toBe("low");
    expect(r.session_id).toBe("");
    expect(r.campus).toBe("all");
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("LLMRequest full overrides all defaults", () => {
    const f = fixtures[8]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    const r = tsResult.result!;
    expect(r.answer_policy).toEqual({ require_citation: true });
    expect(r.output_format).toBe("json");
    expect(r.risk_level).toBe("high");
    expect(r.session_id).toBe("sess_123");
    expect(r.campus).toBe("bj-campus");
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("to_policy_dict minimal output shape", () => {
    const f = fixtures[12]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    const r = tsResult.result!;
    expect(r.task).toBe("admissions_answer");
    expect(typeof r.message).toBe("string");
    expect(typeof r.intent).toBe("string");
    expect(r.scope).toEqual({ role: "visitor", campus: "all" });
    expect(Array.isArray(r.evidence)).toBe(true);
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("to_policy_dict with evidence array", () => {
    const f = fixtures[14]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    const r = tsResult.result!;
    expect(Array.isArray(r.evidence)).toBe(true);
    expect((r.evidence as unknown[]).length).toBe(1);
    const ev = (r.evidence as Record<string, unknown>[])[0]!;
    expect(ev.chunk_id).toBe("c1");
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });

  it("to_prompt_dict returns same fields as EvidenceChunk", () => {
    const f = fixtures[6]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    const r = tsResult.result!;
    const expectedKeys = ["chunk_id", "doc_id", "title", "content", "visibility", "data_level", "allowed_roles", "source_uri"];
    expect(Object.keys(r).sort()).toEqual(expectedKeys.sort());
    expect(deepEqual(tsResult.result, f.output.result)).toBe(true);
  });
});

// --- B: Default Behavior Snapshot ---

describe("B: default behavior snapshot", () => {
  it("from_chunk missing source_uri defaults to ''", () => {
    const f = fixtures[2]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result!.source_uri).toBe("");
  });

  it("from_chunk missing allowed_roles defaults to []", () => {
    const f = fixtures[3]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result!.allowed_roles).toEqual([]);
  });

  it("from_chunk null source_uri becomes 'None' (Python str(None))", () => {
    const f = fixtures[4]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result!.source_uri).toBe("None");
  });

  it("from_chunk null allowed_roles throws TypeError", () => {
    const f = fixtures[5]!;
    expect(f.output.ok).toBe(false);
    expect(f.output.error).toBe("TypeError");
    // TS must also throw
    expect(() => {
      evidenceChunkFromChunk(f.input.chunk as Record<string, unknown>);
    }).toThrow();
  });

  it("LLMRequest answer_policy default is {}", () => {
    const f = fixtures[9]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result!.answer_policy).toEqual({});
  });

  it("LLMRequest empty evidence list works", () => {
    const f = fixtures[11]!;
    const tsResult = runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result!.allowed_evidence).toEqual([]);
  });
});

// --- C: Extra Field Behavior Snapshot ---

describe("C: extra field behavior snapshot", () => {
  it("EvidenceChunk reject extra fields (Python dataclass strict)", () => {
    // Python dataclass with extra kwargs raises TypeError
    // Zod with .strict() also rejects extra fields — matches Python behavior
    const result = EvidenceChunkSchema.safeParse({
      chunk_id: "c1",
      doc_id: "d1",
      title: "T",
      content: "C",
      visibility: "public",
      data_level: "L1",
      allowed_roles: [],
      source_uri: "",
      extra_field: "should_not_be_here",
    });
    expect(result.success).toBe(false);
  });

  it("LLMRequestSchema rejects extra top-level fields (Zod strict)", () => {
    // Python dataclass raises TypeError for unknown kwargs
    // Zod with .strict() also rejects extra fields — matches Python behavior
    const result = LLMRequestSchema.safeParse({
      user_role: "visitor",
      intent: "inquiry",
      user_query: "test",
      allowed_evidence: [],
      unknown_field: "extra",
    });
    expect(result.success).toBe(false);
  });

  it("from_chunk silently ignores extra fields (Python same)", () => {
    // Python's from_chunk only accesses specific keys; extras are ignored
    const result = evidenceChunkFromChunk({
      chunk_id: "c1",
      doc_id: "d1",
      title: "T",
      content: "C",
      visibility: "public",
      data_level: "L1",
      allowed_roles: [],
      source_uri: "",
      extra_ignored: true,
    });
    expect(result.chunk_id).toBe("c1");
    expect("extra_ignored" in result).toBe(false);
  });
});

// --- D: Validation Error Snapshot ---

describe("D: validation error snapshot", () => {
  it("missing required field in EvidenceChunk throws", () => {
    // Python dataclass raises TypeError for missing required field
    expect(() => {
      EvidenceChunkSchema.parse({
        chunk_id: "c1",
        // missing doc_id, title, etc.
      });
    }).toThrow();
  });

  it("missing user_role in LLMRequest throws", () => {
    const f = fixtures[10]!;
    expect(f.output.ok).toBe(false);
    expect(() => {
      LLMRequestSchema.parse({
        intent: "test",
        user_query: "test",
        allowed_evidence: [],
      });
    }).toThrow();
  });

  it("wrong type for allowed_roles throws", () => {
    expect(() => {
      EvidenceChunkSchema.parse({
        chunk_id: "c1",
        doc_id: "d1",
        title: "T",
        content: "C",
        visibility: "public",
        data_level: "L1",
        allowed_roles: "not_a_list",
        source_uri: "",
      });
    }).toThrow();
  });

  it("wrong type for answer_policy throws", () => {
    expect(() => {
      LLMRequestSchema.parse({
        user_role: "visitor",
        intent: "test",
        user_query: "test",
        allowed_evidence: [],
        answer_policy: "should_be_object",
      });
    }).toThrow();
  });

  it("extra top-level field in direct construction: Python rejects, Zod now matches", () => {
    // Python raises TypeError for unknown kwargs.
    // Zod with .strict() now also rejects extra fields — matches Python behavior.
    const result = LLMRequestSchema.safeParse({
      user_role: "visitor",
      intent: "inquiry",
      user_query: "test",
      allowed_evidence: [],
      nonexistent_field: "value",
    });
    expect(result.success).toBe(false);
  });
});

// --- E: Repeated parse stability ---

describe("E: repeated parse stability", () => {
  it("same input produces same output for EvidenceChunk", () => {
    const input = {
      chunk_id: "c1",
      doc_id: "d1",
      title: "T",
      content: "C",
      visibility: "public",
      data_level: "L1",
      allowed_roles: ["visitor"],
      source_uri: "https://example.com",
    };
    const a = EvidenceChunkSchema.parse(input);
    const b = EvidenceChunkSchema.parse(input);
    expect(deepEqual(a, b)).toBe(true);
  });

  it("same input produces same output for LLMRequest", () => {
    const input = {
      user_role: "visitor",
      intent: "inquiry",
      user_query: "test",
      allowed_evidence: [],
    };
    const a = LLMRequestSchema.parse(input);
    const b = LLMRequestSchema.parse(input);
    expect(deepEqual(a, b)).toBe(true);
  });
});
