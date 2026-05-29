import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { canAccess, buildScope } from "../ts-src/index.js";
import type { AccessResult } from "../ts-src/index.js";
import { filterAllowed } from "../../rag-service/ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "permission_service.json");

interface CanAccessFixture {
  input: { item: Record<string, unknown>; scope_role: string; scope_campus?: string };
  output: { ok: boolean; reason: string };
}

const allFixtures: Record<string, unknown>[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as Record<string, unknown>[];

const accessFixtures: CanAccessFixture[] = allFixtures.slice(5) as unknown as CanAccessFixture[];

function toDateStr(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
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

function resultToObj(r: AccessResult): { ok: boolean; reason: string } {
  return { ok: r[0], reason: r[1] };
}

function runPythonCanAccess(
  item: Record<string, unknown>,
  scope: Record<string, unknown>,
  today?: Date,
): AccessResult {
  const tmpScript = resolve(tmpdir(), `access_${randomUUID()}.py`);
  const todayArg = today ? JSON.stringify(toDateStr(today)) : "None";
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
    "from access_checker import can_access",
    `item = json.loads(${JSON.stringify(JSON.stringify(item))})`,
    `scope = json.loads(${JSON.stringify(JSON.stringify(scope))})`,
    `result = can_access(item, scope, ${todayArg})`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    const parsed = JSON.parse(output.trim()) as [boolean, string];
    return parsed;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

function scopeFor(role: string, overrides?: Record<string, unknown>): Record<string, unknown> {
  const id: Record<string, unknown> = {
    user_id: `u_${role}`,
    role,
    campus: "all",
    auth_level: "authenticated",
    ...overrides,
  };
  return buildScope(id, REPO_ROOT);
}

const baseItem: Record<string, unknown> = {
  chunk_id: "c1",
  doc_id: "d1",
  review_status: "approved",
  visibility: "public",
  data_level: "L1",
  allowed_roles: ["visitor", "student", "parent", "customer"],
  campus_scope: ["all"],
  business_tags: [],
  effective_date: "2020-01-01",
  expiry_date: "9999-12-31",
};

// --- Golden Fixture Parity (14 access-checking fixtures: 5 old + 9 null date) ---

describe("golden fixture parity", () => {
  it("fixture 5: data_level_denied (public not in parent scope)", () => {
    const scope = scopeFor("parent");
    const result = canAccess(accessFixtures[0]!.input.item, scope);
    expect(resultToObj(result)).toEqual(accessFixtures[0]!.output);
  });

  it("fixture 6: visibility_denied (internal not in parent scope)", () => {
    const scope = scopeFor("parent");
    const result = canAccess(accessFixtures[1]!.input.item, scope);
    expect(resultToObj(result)).toEqual(accessFixtures[1]!.output);
  });

  it("fixture 7: data_level_denied (public, data_level check before campus)", () => {
    const scope = scopeFor("parent");
    const result = canAccess(accessFixtures[2]!.input.item, scope);
    expect(resultToObj(result)).toEqual(accessFixtures[2]!.output);
  });

  it("fixture 8: data_level_denied (public, data_level check before forbidden)", () => {
    const scope = scopeFor("parent");
    const result = canAccess(accessFixtures[3]!.input.item, scope);
    expect(resultToObj(result)).toEqual(accessFixtures[3]!.output);
  });

  it("fixture 9: data_level_denied (public, data_level check before effective_date)", () => {
    const scope = scopeFor("parent");
    const result = canAccess(accessFixtures[4]!.input.item, scope);
    expect(resultToObj(result)).toEqual(accessFixtures[4]!.output);
  });

  it("all 14 access fixtures match golden JSON", () => {
    for (const fix of accessFixtures) {
      const scope = scopeFor(fix.input.scope_role);
      const tsResult = resultToObj(canAccess(fix.input.item, scope));
      expect(tsResult).toEqual(fix.output);
    }
  });

  it("all 14 access fixtures match live Python can_access", () => {
    for (const fix of accessFixtures) {
      const scope = scopeFor(fix.input.scope_role);
      const tsResult = resultToObj(canAccess(fix.input.item, scope));
      const pyResult = resultToObj(runPythonCanAccess(fix.input.item, scope));
      expect(tsResult).toEqual(pyResult);
    }
  });
});

// --- A: 8-Dimension Decision Snapshot ---

describe("A: 8-dimension decision snapshot", () => {
  it("1. approved + public + L1 + allowed role → allow", () => {
    const result = canAccess(baseItem, scopeFor("visitor"));
    expect(result).toEqual([true, "allowed"]);
  });

  it("2. review_status pending → not_approved", () => {
    const item = { ...baseItem, review_status: "pending" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_approved"]);
  });

  it("3. review_status rejected → not_approved", () => {
    const item = { ...baseItem, review_status: "rejected" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_approved"]);
  });

  it("4. visibility denied (internal not in visitor scope)", () => {
    const item = { ...baseItem, visibility: "internal" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "visibility_denied"]);
  });

  it("5. data_level denied (L2 not in visitor scope)", () => {
    const item = { ...baseItem, data_level: "L2" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "data_level_denied"]);
  });

  it("6. role denied (admin not in item allowed_roles)", () => {
    const scope = scopeFor("admin");
    const result = canAccess(baseItem, scope);
    expect(result).toEqual([false, "role_denied"]);
  });

  it("7. campus_scope denied (bj-campus vs all)", () => {
    const item = { ...baseItem, campus_scope: ["bj-campus"] };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "campus_denied"]);
  });

  it("8. campus_scope all → allow (any campus)", () => {
    const result = canAccess(baseItem, scopeFor("visitor"));
    expect(result).toEqual([true, "allowed"]);
  });

  it("9. forbidden_tag denied (business_tags intersect)", () => {
    const item = { ...baseItem, business_tags: ["internal_pricing"] };
    const scope = scopeFor("visitor");
    const result = canAccess(item, scope);
    expect(result).toEqual([false, "forbidden_tag"]);
  });

  it("10. forbidden_tags empty → allow", () => {
    const item = { ...baseItem, business_tags: [] };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(true);
  });

  it("11. effective_date future → not_effective", () => {
    const item = { ...baseItem, effective_date: "2099-01-01" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_effective"]);
  });

  it("12. expiry_date past → expired", () => {
    const item = { ...baseItem, expiry_date: "2020-01-01" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "expired"]);
  });

  it("all 12 dimension cases match Python live output", () => {
    const cases: Array<{ item: Record<string, unknown>; scope: Record<string, unknown>; label: string }> = [
      { item: baseItem, scope: scopeFor("visitor"), label: "allow" },
      { item: { ...baseItem, review_status: "pending" }, scope: scopeFor("visitor"), label: "pending" },
      { item: { ...baseItem, review_status: "rejected" }, scope: scopeFor("visitor"), label: "rejected" },
      { item: { ...baseItem, visibility: "internal" }, scope: scopeFor("visitor"), label: "visibility" },
      { item: { ...baseItem, data_level: "L2" }, scope: scopeFor("visitor"), label: "data_level" },
      { item: baseItem, scope: scopeFor("admin"), label: "role_admin" },
      { item: { ...baseItem, campus_scope: ["bj-campus"] }, scope: scopeFor("visitor"), label: "campus" },
      { item: { ...baseItem, business_tags: ["internal_pricing"] }, scope: scopeFor("visitor"), label: "forbidden" },
      { item: { ...baseItem, effective_date: "2099-01-01" }, scope: scopeFor("visitor"), label: "effective" },
      { item: { ...baseItem, expiry_date: "2020-01-01" }, scope: scopeFor("visitor"), label: "expired" },
    ];
    for (const c of cases) {
      const tsResult = canAccess(c.item, c.scope);
      const pyResult = runPythonCanAccess(c.item, c.scope);
      expect(tsResult).toEqual(pyResult);
    }
  });
});

// --- B: First Violation Priority Snapshot ---

describe("B: first violation priority snapshot", () => {
  it("not_approved before visibility", () => {
    const item = { ...baseItem, review_status: "pending", visibility: "internal" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_approved"]);
  });

  it("visibility before data_level", () => {
    const item = { ...baseItem, visibility: "internal", data_level: "L2" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "visibility_denied"]);
  });

  it("data_level before role", () => {
    const item = { ...baseItem, data_level: "L2", allowed_roles: ["admin"] };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "data_level_denied"]);
  });

  it("role before campus", () => {
    const scope = scopeFor("admin");
    // item has allowed_roles=["visitor","student","parent","customer"] — scope.role="admin" not in list → role_denied (before campus)
    const item = { ...baseItem, campus_scope: ["bj-campus"] };
    const result = canAccess(item, scope);
    expect(result).toEqual([false, "role_denied"]);
  });

  it("campus before forbidden_tag", () => {
    const item = { ...baseItem, campus_scope: ["bj-campus"], business_tags: ["internal_pricing"] };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "campus_denied"]);
  });

  it("forbidden_tag before not_effective", () => {
    const item = { ...baseItem, business_tags: ["internal_pricing"], effective_date: "2099-01-01" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "forbidden_tag"]);
  });

  it("not_effective before expired", () => {
    const item = { ...baseItem, effective_date: "2099-01-01", expiry_date: "2020-01-01" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_effective"]);
  });

  it("priority order matches Python for multi-violation item", () => {
    const item = {
      ...baseItem,
      review_status: "pending",
      visibility: "internal",
      data_level: "L2",
      campus_scope: ["bj-campus"],
      business_tags: ["internal_pricing"],
      effective_date: "2099-01-01",
      expiry_date: "2020-01-01",
    };
    const tsResult = canAccess(item, scopeFor("visitor"));
    const pyResult = runPythonCanAccess(item, scopeFor("visitor"));
    expect(tsResult).toEqual(pyResult);
  });
});

// --- C: Missing Field Behavior Snapshot ---

describe("C: missing field behavior snapshot", () => {
  it("missing review_status → not_approved (None != 'approved')", () => {
    const item = { ...baseItem };
    delete item.review_status;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "not_approved"]);
  });

  it("missing visibility → visibility_denied", () => {
    const item = { ...baseItem };
    delete item.visibility;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "visibility_denied"]);
  });

  it("missing data_level → data_level_denied", () => {
    const item = { ...baseItem };
    delete item.data_level;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "data_level_denied"]);
  });

  it("missing allowed_roles → role_denied (empty [])", () => {
    const item = { ...baseItem };
    delete item.allowed_roles;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "role_denied"]);
  });

  it("missing campus_scope → campus_denied (empty [])", () => {
    const item = { ...baseItem };
    delete item.campus_scope;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "campus_denied"]);
  });

  it("missing business_tags → allowed (treated as empty set)", () => {
    const item = { ...baseItem };
    delete item.business_tags;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(true);
  });

  it("missing effective_date → allowed (defaults to 0000-01-01 < today)", () => {
    const item = { ...baseItem };
    delete item.effective_date;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(true);
  });

  it("missing expiry_date → allowed (defaults to 9999-12-31 > today)", () => {
    const item = { ...baseItem };
    delete item.expiry_date;
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(true);
  });

  it("missing scope role → role_denied (undefined not in list)", () => {
    const scope = scopeFor("visitor");
    delete scope.role;
    const result = canAccess(baseItem, scope);
    expect(result).toEqual([false, "role_denied"]);
  });

  it("missing scope campus → campus_denied (undefined not in list)", () => {
    const scope = scopeFor("visitor");
    delete scope.campus;
    const result = canAccess({ ...baseItem, campus_scope: ["bj-campus"] }, scope);
    expect(result).toEqual([false, "campus_denied"]);
  });

  it("all missing field cases match Python baseline", () => {
    const cases: Array<{ item: Record<string, unknown>; scope: Record<string, unknown>; label: string }> = [
      { item: (() => { const i = { ...baseItem }; delete i.review_status; return i; })(), scope: scopeFor("visitor"), label: "missing_review_status" },
      { item: (() => { const i = { ...baseItem }; delete i.visibility; return i; })(), scope: scopeFor("visitor"), label: "missing_visibility" },
      { item: (() => { const i = { ...baseItem }; delete i.data_level; return i; })(), scope: scopeFor("visitor"), label: "missing_data_level" },
      { item: (() => { const i = { ...baseItem }; delete i.allowed_roles; return i; })(), scope: scopeFor("visitor"), label: "missing_allowed_roles" },
      { item: (() => { const i = { ...baseItem }; delete i.campus_scope; return i; })(), scope: scopeFor("visitor"), label: "missing_campus_scope" },
      { item: (() => { const i = { ...baseItem }; delete i.business_tags; return i; })(), scope: scopeFor("visitor"), label: "missing_business_tags" },
      { item: (() => { const i = { ...baseItem }; delete i.effective_date; return i; })(), scope: scopeFor("visitor"), label: "missing_effective_date" },
      { item: (() => { const i = { ...baseItem }; delete i.expiry_date; return i; })(), scope: scopeFor("visitor"), label: "missing_expiry_date" },
    ];
    for (const c of cases) {
      const tsResult = canAccess(c.item, c.scope);
      const pyResult = runPythonCanAccess(c.item, c.scope);
      expect(tsResult).toEqual(pyResult);
    }
  });
});

// --- Null Date Fixture Tests ---

describe("null date fixtures", () => {
  const nullFixtureStart = 5; // old access fixtures occupy indices 0-4

  it("fixture 10: effective_date null, expiry_date missing → not_effective", () => {
    const fix = accessFixtures[nullFixtureStart + 0]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: false, reason: "not_effective" });
  });

  it("fixture 11: expiry_date null, effective_date missing → allowed", () => {
    const fix = accessFixtures[nullFixtureStart + 1]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: true, reason: "allowed" });
  });

  it("fixture 12: effective_date null, expiry_date null → not_effective (checked first)", () => {
    const fix = accessFixtures[nullFixtureStart + 2]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: false, reason: "not_effective" });
  });

  it("fixture 13: effective_date '', expiry_date missing → allowed ('0000-01-01' default)", () => {
    const fix = accessFixtures[nullFixtureStart + 3]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: true, reason: "allowed" });
  });

  it("fixture 14: expiry_date '', effective_date missing → expired ('' < today)", () => {
    const fix = accessFixtures[nullFixtureStart + 4]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: false, reason: "expired" });
  });

  it("fixture 15: effective_date 'None' string, expiry_date missing → not_effective", () => {
    const fix = accessFixtures[nullFixtureStart + 5]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: false, reason: "not_effective" });
  });

  it("fixture 16: expiry_date 'None' string, effective_date missing → allowed", () => {
    const fix = accessFixtures[nullFixtureStart + 6]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: true, reason: "allowed" });
  });

  it("fixture 17: effective_date 'null' string, expiry_date missing → not_effective", () => {
    const fix = accessFixtures[nullFixtureStart + 7]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: false, reason: "not_effective" });
  });

  it("fixture 18: expiry_date 'null' string, effective_date missing → allowed", () => {
    const fix = accessFixtures[nullFixtureStart + 8]!;
    const scope = scopeFor(fix.input.scope_role);
    const result = canAccess(fix.input.item, scope);
    expect(resultToObj(result)).toEqual({ ok: true, reason: "allowed" });
  });

  it("all 9 null date fixtures match Python live output", () => {
    for (let i = 0; i < 9; i++) {
      const fix = accessFixtures[nullFixtureStart + i]!;
      const scope = scopeFor(fix.input.scope_role);
      const tsResult = resultToObj(canAccess(fix.input.item, scope));
      const pyResult = resultToObj(runPythonCanAccess(fix.input.item, scope));
      expect(tsResult).toEqual(pyResult);
    }
  });
});

// --- D: MetadataFilter Semantic Audit ---

describe("D: metadataFilter semantic audit", () => {
  it("accessChecker and metadataFilter agree on base allow case", () => {
    const scope = scopeFor("visitor");
    const acResult = canAccess(baseItem, scope);
    const [allowed] = filterAllowed([baseItem], scope);
    expect(acResult[0]).toBe(true);
    expect(allowed.length).toBe(1);
  });

  it("accessChecker and metadataFilter agree on not_approved", () => {
    const item = { ...baseItem, review_status: "pending" };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult).toEqual([false, "not_approved"]);
    expect(denied[0]!.reason).toBe("not_approved");
  });

  it("accessChecker and metadataFilter agree on visibility_denied", () => {
    const item = { ...baseItem, visibility: "internal" };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult).toEqual([false, "visibility_denied"]);
    expect(denied[0]!.reason).toBe("visibility_denied");
  });

  it("accessChecker and metadataFilter agree on data_level_denied", () => {
    const item = { ...baseItem, data_level: "L2" };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult).toEqual([false, "data_level_denied"]);
    expect(denied[0]!.reason).toBe("data_level_denied");
  });

  it("accessChecker and metadataFilter agree on role_denied", () => {
    const scope = scopeFor("admin");
    const acResult = canAccess(baseItem, scope);
    const [, denied] = filterAllowed([baseItem], scope);
    expect(acResult).toEqual([false, "role_denied"]);
    expect(denied[0]!.reason).toBe("role_denied");
  });

  it("accessChecker and metadataFilter agree on campus_denied", () => {
    const item = { ...baseItem, campus_scope: ["bj-campus"] };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult).toEqual([false, "campus_denied"]);
    expect(denied[0]!.reason).toBe("campus_denied");
  });

  it("accessChecker and metadataFilter agree on forbidden_tag", () => {
    const item = { ...baseItem, business_tags: ["internal_pricing"] };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult).toEqual([false, "forbidden_tag"]);
    expect(denied[0]!.reason).toBe("forbidden_tag");
  });

  it("accessChecker and metadataFilter agree on multi-violation first win", () => {
    const item = {
      ...baseItem,
      review_status: "pending",
      visibility: "internal",
      data_level: "L2",
      campus_scope: ["bj-campus"],
      business_tags: ["internal_pricing"],
    };
    const scope = scopeFor("visitor");
    const acResult = canAccess(item, scope);
    const [, denied] = filterAllowed([item], scope);
    expect(acResult[1]).toBe(denied[0]!.reason);
  });
});

// --- All 9 roles x representative metadata ---

describe("all 9 roles against representative metadata", () => {
  const roles = ["visitor", "customer", "student", "parent", "sales",
                 "teacher", "operator", "campus_admin", "admin"];

  for (const role of roles) {
    it(`${role}: public L1 data with matching allowed_roles → allowed`, () => {
      const allowedRoles = ["visitor", "student", "parent", "customer", "sales",
                            "teacher", "operator", "campus_admin", "admin"];
      const item = { ...baseItem, allowed_roles: allowedRoles };
      const scope = scopeFor(role);
      const result = canAccess(item, scope);
      expect(result[0]).toBe(true);
    });
  }

  it("sales can access internal data (L3)", () => {
    const item = { ...baseItem, visibility: "internal", data_level: "L3", allowed_roles: ["visitor", "student", "parent", "sales"] };
    const result = canAccess(item, scopeFor("sales"));
    expect(result[0]).toBe(true);
  });

  it("admin can access internal data (L4)", () => {
    const item = { ...baseItem, visibility: "internal", data_level: "L4", allowed_roles: ["admin"] };
    const result = canAccess(item, scopeFor("admin"));
    expect(result[0]).toBe(true);
  });

  it("visitor cannot access internal data", () => {
    const item = { ...baseItem, visibility: "internal", data_level: "L3" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([false, "visibility_denied"]);
  });
});

// --- Repeatable calls stable ---

describe("repeatable calls stable", () => {
  it("same inputs produce same outputs", () => {
    const a = canAccess(baseItem, scopeFor("visitor"));
    const b = canAccess(baseItem, scopeFor("visitor"));
    expect(a).toEqual(b);
  });
});

// --- Allowed denied payload shapes ---

describe("result payload shape", () => {
  it("allowed returns [true, 'allowed']", () => {
    const result = canAccess(baseItem, scopeFor("visitor"));
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBe(2);
    expect(typeof result[0]).toBe("boolean");
    expect(typeof result[1]).toBe("string");
  });

  it("denied returns [false, reason_string]", () => {
    const item = { ...baseItem, review_status: "pending" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(false);
    expect(typeof result[1]).toBe("string");
    expect(result[1].length).toBeGreaterThan(0);
  });
});

// --- Date string lexical comparison ---

describe("date string lexical comparison", () => {
  it("effective_date '2000-01-01' < today → allowed", () => {
    const item = { ...baseItem, effective_date: "2000-01-01" };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result[0]).toBe(true);
  });

  it("effective_date exactly today → allowed (not >)", () => {
    const today = new Date();
    const todayStr = toDateStr(today);
    const item = { ...baseItem, effective_date: todayStr };
    const result = canAccess(item, scopeFor("visitor"), today);
    expect(result[0]).toBe(true);
  });

  it("expiry_date exactly today → allowed (not <)", () => {
    const today = new Date();
    const todayStr = toDateStr(today);
    const item = { ...baseItem, expiry_date: todayStr };
    const result = canAccess(item, scopeFor("visitor"), today);
    expect(result[0]).toBe(true);
  });

  it("date comparison uses lexical string compare, not Date object", () => {
    const today = new Date("2026-06-15");
    const item = { ...baseItem, effective_date: "2026-01-01", expiry_date: "2026-12-31" };
    const result = canAccess(item, scopeFor("visitor"), today);
    expect(result[0]).toBe(true);
  });
});

// --- Unknown metadata fields ---

describe("unknown metadata fields", () => {
  it("unknown fields in item are ignored during access check", () => {
    const item = { ...baseItem, unknown_field: "ignored", score: 0.95 };
    const result = canAccess(item, scopeFor("visitor"));
    expect(result).toEqual([true, "allowed"]);
  });

  it("unknown fields in scope are ignored", () => {
    const scope = { ...scopeFor("visitor"), extra_scope_field: "ignored" };
    const result = canAccess(baseItem, scope);
    expect(result).toEqual([true, "allowed"]);
  });
});
