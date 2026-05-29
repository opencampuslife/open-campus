import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { filterAllowed } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "metadata_filter.json");

interface FixtureCase {
  input: { chunks: Record<string, unknown>[]; scope: Record<string, unknown> };
  output: [Record<string, unknown>[], Record<string, unknown>[]];
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonFilter(
  chunks: Record<string, unknown>[],
  scope: Record<string, unknown>,
): [Record<string, unknown>[], Record<string, unknown>[]] {
  const tmpScript = resolve(tmpdir(), `parity_mdf_${randomUUID()}.py`);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "rag-service", "src"))})`,
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
    "from metadata_filter import filter_allowed",
    `result = filter_allowed(json.loads(${JSON.stringify(JSON.stringify(chunks))}), json.loads(${JSON.stringify(JSON.stringify(scope))}))`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as [Record<string, unknown>[], Record<string, unknown>[]];
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
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

// --- Golden Fixture Parity ---

describe("metadataFilter: golden fixture parity", () => {
  it("matches stored golden JSON output for all 6 fixtures", () => {
    for (const c of fixtures) {
      const tsOut = filterAllowed(c.input.chunks, c.input.scope);
      expect(deepEqual(tsOut, c.output)).toBe(true);
    }
  });

  it("matches live Python output for all 6 fixtures", () => {
    for (const c of fixtures) {
      const tsOut = filterAllowed(c.input.chunks, c.input.scope);
      const pyOut = runPythonFilter(c.input.chunks, c.input.scope);
      expect(deepEqual(tsOut, pyOut)).toBe(true);
    }
  });

  it("fixture 1: normal metadata -> allowed", () => {
    const [allowed, denied] = filterAllowed(fixtures[0]!.input.chunks, fixtures[0]!.input.scope);
    expect(allowed.length).toBe(1);
    expect(denied.length).toBe(0);
  });

  it("fixture 2: forbidden_tag -> denied", () => {
    const [allowed, denied] = filterAllowed(fixtures[1]!.input.chunks, fixtures[1]!.input.scope);
    expect(allowed.length).toBe(0);
    expect(denied.length).toBe(1);
    expect(denied[0]!.reason).toBe("forbidden_tag");
  });

  it("fixture 3: mixed visibility + forbidden_tag -> partial deny", () => {
    const [allowed, denied] = filterAllowed(fixtures[2]!.input.chunks, fixtures[2]!.input.scope);
    expect(allowed.length).toBe(1);
    expect(allowed[0]!.chunk_id).toBe("c1");
    expect(denied.length).toBe(2);
    expect(denied[0]!.reason).toBe("visibility_denied");
    expect(denied[1]!.reason).toBe("forbidden_tag");
  });

  it("fixture 4: not_approved -> denied", () => {
    const [allowed, denied] = filterAllowed(fixtures[3]!.input.chunks, fixtures[3]!.input.scope);
    expect(allowed.length).toBe(0);
    expect(denied.length).toBe(1);
    expect(denied[0]!.reason).toBe("not_approved");
  });

  it("fixture 5: empty chunks -> empty result", () => {
    const [allowed, denied] = filterAllowed(fixtures[4]!.input.chunks, fixtures[4]!.input.scope);
    expect(allowed).toEqual([]);
    expect(denied).toEqual([]);
  });

  it("fixture 6: null/empty date variations -> 4 allowed, 5 denied", () => {
    const [allowed, denied] = filterAllowed(fixtures[5]!.input.chunks, fixtures[5]!.input.scope);
    expect(allowed.length).toBe(4);
    expect(denied.length).toBe(5);
    expect(denied.filter(d => d.reason === "not_effective").length).toBe(4);
    expect(denied.filter(d => d.reason === "expired").length).toBe(1);
  });

  it("fixture 6: null date denies not_effective before expired priority", () => {
    const [allowed, denied] = filterAllowed(fixtures[5]!.input.chunks, fixtures[5]!.input.scope);
    // c_null_2 has both effective_date=null AND expiry_date=null
    // not_effective check runs before expired check
    const c2 = denied.find(d => d.chunk_id === "c_null_2");
    expect(c2?.reason).toBe("not_effective");
  });
});

// --- Filter Decision Snapshots ---

describe("metadataFilter: decision snapshots", () => {
  const baseScope = {
    role: "visitor",
    campus: "all",
    auth_level: "public",
    allowed_visibility: ["public"],
    allowed_data_levels: ["public"],
    allowed_roles: ["visitor"],
    forbidden_tags: ["internal_pricing", "sales_script"],
  };

  const approvedChunk = {
    chunk_id: "c1",
    doc_id: "d1",
    review_status: "approved",
    visibility: "public",
    data_level: "public",
    allowed_roles: ["visitor"],
    campus_scope: ["all"],
    business_tags: [],
    effective_date: "2020-01-01",
    expiry_date: "9999-12-31",
  };

  it("visibility denied", () => {
    const chunk = { ...approvedChunk, visibility: "internal" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("visibility_denied");
  });

  it("data_level denied", () => {
    const chunk = { ...approvedChunk, data_level: "confidential" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("data_level_denied");
  });

  it("role denied", () => {
    const chunk = { ...approvedChunk, allowed_roles: ["sales"] };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("role_denied");
  });

  it("campus denied: scope campus not in chunk campus_scope", () => {
    const scope = { ...baseScope, campus: "bj" };
    const chunk = { ...approvedChunk, campus_scope: ["sh"] };
    const [allowed, denied] = filterAllowed([chunk], scope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("campus_denied");
  });

  it("campus allowed: scope campus matches campus_scope", () => {
    const scope = { ...baseScope, campus: "bj" };
    const chunk = { ...approvedChunk, campus_scope: ["bj"] };
    const [allowed, denied] = filterAllowed([chunk], scope);
    expect(allowed.length).toBe(1);
  });

  it("campus allowed: chunk campus_scope contains 'all'", () => {
    const scope = { ...baseScope, campus: "bj" };
    const chunk = { ...approvedChunk, campus_scope: ["all"] };
    const [allowed, denied] = filterAllowed([chunk], scope);
    expect(allowed.length).toBe(1);
  });

  it("forbidden_tag denies", () => {
    const chunk = { ...approvedChunk, business_tags: ["internal_pricing"] };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("forbidden_tag");
  });

  it("not_approved when review_status is pending", () => {
    const chunk = { ...approvedChunk, review_status: "pending" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("not_approved");
  });

  it("not_approved when review_status is rejected", () => {
    const chunk = { ...approvedChunk, review_status: "rejected" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("not_approved");
  });
});

// --- Edge Cases ---

describe("metadataFilter: edge cases", () => {
  const baseScope = {
    role: "visitor",
    campus: "all",
    auth_level: "public",
    allowed_visibility: ["public"],
    allowed_data_levels: ["public"],
    allowed_roles: ["visitor"],
    forbidden_tags: ["internal_pricing", "sales_script"],
  };

  const baseChunk = {
    chunk_id: "c1",
    doc_id: "d1",
    review_status: "approved",
    visibility: "public",
    data_level: "public",
    allowed_roles: ["visitor"],
    campus_scope: ["all"],
    business_tags: [],
    effective_date: "2020-01-01",
    expiry_date: "9999-12-31",
  };

  it("metadata missing visibility -> denied (None not in allowed)", () => {
    const chunk = { ...baseChunk };
    delete chunk.visibility;
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("visibility_denied");
  });

  it("metadata missing data_level -> denied", () => {
    const chunk = { ...baseChunk };
    delete chunk.data_level;
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("data_level_denied");
  });

  it("metadata missing campus_scope -> denied (empty [])", () => {
    const chunk = { ...baseChunk };
    delete chunk.campus_scope;
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(denied[0]!.reason).toBe("campus_denied");
  });

  it("metadata tags is empty array -> allowed", () => {
    const chunk = { ...baseChunk, business_tags: [] };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(1);
  });

  it("metadata tags missing -> allowed (treated as empty)", () => {
    const chunk = { ...baseChunk };
    delete chunk.business_tags;
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(1);
  });

  it("empty chunks array -> empty result", () => {
    const [allowed, denied] = filterAllowed([], baseScope);
    expect(allowed).toEqual([]);
    expect(denied).toEqual([]);
  });

  it("single chunk allowed -> correct output", () => {
    const [allowed, denied] = filterAllowed([baseChunk], baseScope);
    expect(allowed.length).toBe(1);
    expect(allowed[0]!.chunk_id).toBe("c1");
    expect(denied.length).toBe(0);
  });

  it("unknown fields in chunk are preserved in allowed output", () => {
    const chunk = { ...baseChunk, extra_field: "should_preserve" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(denied.length).toBe(0);
    expect(allowed[0]!.extra_field).toBe("should_preserve");
  });

  it("denied entry only has chunk_id, doc_id, reason (not full metadata)", () => {
    const chunk = { ...baseChunk, visibility: "internal" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(allowed.length).toBe(0);
    expect(Object.keys(denied[0]!)).toEqual(["chunk_id", "doc_id", "reason"]);
  });

  it("non-allowed role denied: admin role not in allowed_roles", () => {
    const scope2 = { ...baseScope, role: "admin" };
    const [allowed, denied] = filterAllowed([baseChunk], scope2);
    expect(denied[0]!.reason).toBe("role_denied");
  });

  it("first violation reason is returned (stops at first check)", () => {
    // chunk has BOTH review_status=pending AND visibility=internal
    // should stop at not_approved (first check)
    const chunk = { ...baseChunk, review_status: "pending", visibility: "internal" };
    const [allowed, denied] = filterAllowed([chunk], baseScope);
    expect(denied[0]!.reason).toBe("not_approved");
  });
});

// --- Order Stability ---

describe("metadataFilter: order stability", () => {
  const baseScope = {
    role: "visitor",
    campus: "all",
    auth_level: "public",
    allowed_visibility: ["public"],
    allowed_data_levels: ["public"],
    allowed_roles: ["visitor"],
    forbidden_tags: ["internal_pricing", "sales_script"],
  };

  const makeChunk = (id: string, visibility: string, reviewStatus = "approved") => ({
    chunk_id: id,
    doc_id: `d_${id}`,
    review_status: reviewStatus,
    visibility,
    data_level: "public",
    allowed_roles: ["visitor"],
    campus_scope: ["all"],
    business_tags: [],
    effective_date: "2020-01-01",
    expiry_date: "9999-12-31",
  });

  it("mixed allowed/denied preserves input order in both output arrays", () => {
    const chunks = [
      makeChunk("c1", "public"),
      makeChunk("c2", "internal"),
      makeChunk("c3", "public"),
      makeChunk("c4", "internal"),
    ];
    const [allowed, denied] = filterAllowed(chunks, baseScope);
    expect(allowed.map((c) => c.chunk_id)).toEqual(["c1", "c3"]);
    expect(denied.map((c) => c.chunk_id)).toEqual(["c2", "c4"]);
  });

  it("all denied preserves input order", () => {
    const chunks = [
      makeChunk("z", "internal"),
      makeChunk("a", "internal"),
      makeChunk("m", "internal"),
    ];
    const [allowed, denied] = filterAllowed(chunks, baseScope);
    expect(allowed).toEqual([]);
    expect(denied.map((c) => c.chunk_id)).toEqual(["z", "a", "m"]);
  });

  it("all allowed preserves input order", () => {
    const chunks = [
      makeChunk("c3", "public"),
      makeChunk("c1", "public"),
      makeChunk("c2", "public"),
    ];
    const [allowed, denied] = filterAllowed(chunks, baseScope);
    expect(allowed.map((c) => c.chunk_id)).toEqual(["c3", "c1", "c2"]);
    expect(denied).toEqual([]);
  });

  it("order matches Python for shuffled input", () => {
    const chunks = [
      makeChunk("cB", "public"),
      makeChunk("cA", "internal"),
      makeChunk("cC", "public"),
      makeChunk("cD", "internal"),
    ];
    const tsOut = filterAllowed(chunks, baseScope);
    const pyOut = runPythonFilter(chunks, baseScope);
    expect(deepEqual(tsOut, pyOut)).toBe(true);
  });
});

// --- Denied entry structure ---

describe("metadataFilter: denied entry structure", () => {
  it("denied entry has chunk_id, doc_id, reason only", () => {
    const chunk = {
      chunk_id: "test_id",
      doc_id: "test_doc",
      review_status: "pending",
      visibility: "public",
      data_level: "public",
      allowed_roles: ["visitor"],
      campus_scope: ["all"],
      business_tags: [],
      effective_date: "2020-01-01",
      expiry_date: "9999-12-31",
    };
    const [allowed, denied] = filterAllowed([chunk], {
      role: "visitor",
      campus: "all",
      auth_level: "public",
      allowed_visibility: ["public"],
      allowed_data_levels: ["public"],
      allowed_roles: ["visitor"],
      forbidden_tags: [],
    });
    expect(denied[0]).toEqual({
      chunk_id: "test_id",
      doc_id: "test_doc",
      reason: "not_approved",
    });
    expect(allowed.length).toBe(0);
  });
});

// --- Live Python byte-level comparison ---

describe("metadataFilter: byte-level Python comparison", () => {
  it("produces identical JSON output to Python", () => {
    const chunks = [
      {
        chunk_id: "c1",
        doc_id: "d1",
        review_status: "approved",
        visibility: "public",
        data_level: "public",
        allowed_roles: ["visitor"],
        campus_scope: ["all"],
        business_tags: [],
        effective_date: "2020-01-01",
        expiry_date: "9999-12-31",
      },
    ];
    const scope = {
      role: "visitor",
      campus: "all",
      auth_level: "public",
      allowed_visibility: ["public"],
      allowed_data_levels: ["public"],
      allowed_roles: ["visitor"],
      forbidden_tags: ["internal_pricing"],
    };
    const tsOut = filterAllowed(chunks, scope);
    const pyOut = runPythonFilter(chunks, scope);
    expect(JSON.stringify(tsOut)).toBe(JSON.stringify(pyOut));
  });
});
