import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { loadRoles, loadDataLevels, loadRetrievalPolicy, loadAllPolicies } from "../ts-src/index.js";
import { parse } from "yaml";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");

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

function runPythonLoadRoles(): Record<string, unknown> {
  const tmpScript = resolve(tmpdir(), `policy_role_${randomUUID()}.py`);
  const script = [
    "import json, sys, pathlib",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "knowledge-service", "src"))})`,
    "from policy_loader import load_roles",
    `result = load_roles(pathlib.Path(${JSON.stringify(REPO_ROOT)}))`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as Record<string, unknown>;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

function runPythonRawYaml(relativePath: string): Record<string, unknown> {
  const tmpScript = resolve(tmpdir(), `policy_raw_${randomUUID()}.py`);
  const script = [
    "import json, sys, pathlib",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "knowledge-service", "src"))})`,
    "from simple_yaml import load_file",
    `result = load_file(pathlib.Path(${JSON.stringify(resolve(REPO_ROOT, relativePath))}))`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 15_000,
    });
    return JSON.parse(output.trim()) as Record<string, unknown>;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

// --- Raw YAML Parse Snapshot (A) ---

describe("A: raw YAML parse snapshot", () => {
  it("roles.yaml raw parse matches Python simple_yaml output", () => {
    const pyRaw = runPythonRawYaml("configs/roles.yaml");
    const tsRaw = parse(readFileSync(resolve(REPO_ROOT, "configs/roles.yaml"), "utf-8"));
    expect(deepEqual(tsRaw, pyRaw)).toBe(true);
  });

  it("data_levels.yaml raw parse matches Python", () => {
    const pyRaw = runPythonRawYaml("configs/data_levels.yaml");
    const tsRaw = parse(readFileSync(resolve(REPO_ROOT, "configs/data_levels.yaml"), "utf-8"));
    expect(deepEqual(tsRaw, pyRaw)).toBe(true);
  });

  it("retrieval_policy.yaml raw parse matches Python", () => {
    const pyRaw = runPythonRawYaml("configs/retrieval_policy.yaml");
    const tsRaw = parse(readFileSync(resolve(REPO_ROOT, "configs/retrieval_policy.yaml"), "utf-8"));
    expect(deepEqual(tsRaw, pyRaw)).toBe(true);
  });

  it("roles.yaml key order is consistent with Python", () => {
    const pyRaw = runPythonRawYaml("configs/roles.yaml");
    const tsRaw = parse(readFileSync(resolve(REPO_ROOT, "configs/roles.yaml"), "utf-8")) as Record<string, unknown>;
    const rolesPy = (pyRaw.roles as Record<string, unknown>) ?? {};
    const rolesTs = (tsRaw.roles as Record<string, unknown>) ?? {};
    expect(Object.keys(rolesTs)).toEqual(Object.keys(rolesPy));
  });

  it("data_levels.yaml key order is consistent with Python", () => {
    const pyRaw = runPythonRawYaml("configs/data_levels.yaml");
    const tsRaw = parse(readFileSync(resolve(REPO_ROOT, "configs/data_levels.yaml"), "utf-8")) as Record<string, unknown>;
    const dlPy = (pyRaw.data_levels as Record<string, unknown>) ?? {};
    const dlTs = (tsRaw.data_levels as Record<string, unknown>) ?? {};
    expect(Object.keys(dlTs)).toEqual(Object.keys(dlPy));
  });
});

// --- Public Loader Output Snapshot (B) ---

describe("B: public loader output snapshot", () => {
  it("loadRoles output matches Python load_roles", () => {
    const pyRoles = runPythonLoadRoles();
    const tsRoles = loadRoles(REPO_ROOT);
    expect(deepEqual(tsRoles, pyRoles)).toBe(true);
  });

  it("loadRoles returns correct structure for visitor role", () => {
    const roles = loadRoles(REPO_ROOT);
    const visitor = roles.visitor as Record<string, unknown>;
    expect(visitor.description).toBe("Unauthenticated website or H5 visitor.");
    expect(visitor.allowed_visibility).toEqual(["public"]);
    expect(visitor.allowed_data_levels).toEqual(["L1"]);
  });

  it("loadRoles returns correct structure for sales role", () => {
    const roles = loadRoles(REPO_ROOT);
    const sales = roles.sales as Record<string, unknown>;
    expect(sales.allowed_visibility).toEqual(["public", "protected", "internal"]);
    expect(sales.allowed_data_levels).toEqual(["L1", "L2", "L3"]);
    expect(sales.campus_scoped).toBe(true);
  });

  it("loadRoles returns correct structure for teacher role with forbidden_tags", () => {
    const roles = loadRoles(REPO_ROOT);
    const teacher = roles.teacher as Record<string, unknown>;
    expect(teacher.forbidden_tags).toEqual(["crm_rule", "deal_info", "internal_pricing"]);
  });

  it("loadRoles returns correct structure for admin role (highest privileges)", () => {
    const roles = loadRoles(REPO_ROOT);
    const admin = roles.admin as Record<string, unknown>;
    expect(admin.allowed_visibility).toEqual(["public", "protected", "internal", "admin"]);
    expect(admin.allowed_data_levels).toEqual(["L1", "L2", "L3", "L4"]);
    // admin has no campus_scoped and no forbidden_tags
    expect(admin.campus_scoped).toBeUndefined();
    expect(admin.forbidden_tags).toBeUndefined();
  });

  it("loadRoles key order matches YAML definition order", () => {
    const roles = loadRoles(REPO_ROOT);
    const keys = Object.keys(roles);
    expect(keys).toEqual([
      "visitor", "customer", "student", "parent",
      "sales", "teacher", "operator", "campus_admin", "admin",
    ]);
  });

  it("loadRoles returns same result for repeated calls", () => {
    const a = loadRoles(REPO_ROOT);
    const b = loadRoles(REPO_ROOT);
    expect(deepEqual(a, b)).toBe(true);
  });

  it("loadDataLevels returns correct structure", () => {
    const dl = loadDataLevels(REPO_ROOT);
    const l1 = dl.L1 as Record<string, unknown>;
    expect(l1.name).toBe("Public");
    expect(l1.user_visible).toBe(true);
    const l4 = dl.L4 as Record<string, unknown>;
    expect(l4.name).toBe("Sensitive");
    expect(l4.user_visible).toBe(false);
  });

  it("loadDataLevels key order matches YAML", () => {
    const dl = loadDataLevels(REPO_ROOT);
    expect(Object.keys(dl)).toEqual(["L1", "L2", "L3", "L4"]);
  });

  it("loadRetrievalPolicy returns correct structure", () => {
    const rp = loadRetrievalPolicy(REPO_ROOT);
    const defaults = rp.defaults as Record<string, unknown>;
    expect(defaults.min_confidence).toBe(0.65);
    expect(defaults.max_chunks).toBe(8);
    const hybrid = defaults.hybrid_search as Record<string, unknown>;
    expect(hybrid.vector_weight).toBe(0.7);
    expect(hybrid.keyword_weight).toBe(0.3);
  });

  it("loadRetrievalPolicy pre_filter structure", () => {
    const rp = loadRetrievalPolicy(REPO_ROOT);
    const pre = rp.pre_filter as Record<string, unknown>;
    const required = pre.required as string[];
    expect(required).toContain("review_status == approved");
    expect(required).toContain("expiry_date >= today");
    const forbidden = pre.forbidden as string[];
    expect(forbidden[0]).toContain("business_tags intersects");
  });

  it("loadAllPolicies returns all three policies", () => {
    const all = loadAllPolicies(REPO_ROOT);
    expect(all.roles.visitor).toBeDefined();
    expect(all.dataLevels.L1).toBeDefined();
    expect(all.retrievalPolicy.defaults).toBeDefined();
  });
});

// --- Role default value behaviors ---

describe("role field defaults and edge cases", () => {
  it("visitor role has no campus_scoped (defaults to undefined)", () => {
    const roles = loadRoles(REPO_ROOT);
    const visitor = roles.visitor as Record<string, unknown>;
    expect(visitor.campus_scoped).toBeUndefined();
  });

  it("sales role has campus_scoped: true", () => {
    const roles = loadRoles(REPO_ROOT);
    const sales = roles.sales as Record<string, unknown>;
    expect(sales.campus_scoped).toBe(true);
  });

  it("visitor role has no forbidden_tags (defaults to undefined)", () => {
    const roles = loadRoles(REPO_ROOT);
    const visitor = roles.visitor as Record<string, unknown>;
    expect(visitor.forbidden_tags).toBeUndefined();
  });

  it("teacher role has forbidden_tags", () => {
    const roles = loadRoles(REPO_ROOT);
    const teacher = roles.teacher as Record<string, unknown>;
    expect(teacher.forbidden_tags).toEqual(["crm_rule", "deal_info", "internal_pricing"]);
  });

  it("operator role has forbidden_tags", () => {
    const roles = loadRoles(REPO_ROOT);
    const op = roles.operator as Record<string, unknown>;
    expect(op.forbidden_tags).toEqual(["student_private_case"]);
  });
});

// --- Edge Cases ---

describe("error behavior snapshot (C)", () => {
  const fakeRoot = resolve(tmpdir(), "no_such_project");

  it("throws for missing YAML file", () => {
    expect(() => loadRoles(fakeRoot)).toThrow();
  });

  it("error message mentions the missing file path", () => {
    expect(() => loadRoles(fakeRoot)).toThrow(/roles\.yaml|ENOENT|no such file/i);
  });

  it("Python also throws for missing YAML file", () => {
    const tmpScript = resolve(tmpdir(), `policy_err_${randomUUID()}.py`);
    const script = [
      "import sys, pathlib",
      `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
      `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "knowledge-service", "src"))})`,
      "from policy_loader import load_roles",
      `load_roles(pathlib.Path(${JSON.stringify(fakeRoot)}))`,
    ].join("\n");
    writeFileSync(tmpScript, script, "utf-8");
    expect(() => {
      execSync(`python3 ${JSON.stringify(tmpScript)}`, {
        cwd: REPO_ROOT,
        encoding: "utf-8",
        timeout: 10_000,
      });
    }).toThrow();
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  });

  it("invalid YAML throws error", () => {
    const badYaml = resolve(tmpdir(), `bad_${randomUUID()}.yaml`);
    writeFileSync(badYaml, "key: [unclosed", "utf-8");
    expect(() => {
      parse(readFileSync(badYaml, "utf-8"));
    }).toThrow();
    try { unlinkSync(badYaml); } catch { /* ignore */ }
  });
});

// --- Unknown field preservation ---

describe("unknown field behavior", () => {
  it("visitor role has only known fields (no extra fields)", () => {
    const roles = loadRoles(REPO_ROOT);
    const visitor = roles.visitor as Record<string, unknown>;
    const keys = Object.keys(visitor).sort();
    expect(keys).toEqual(["allowed_data_levels", "allowed_visibility", "description"]);
  });

  it("campus_admin role has campus_scoped field", () => {
    const roles = loadRoles(REPO_ROOT);
    const ca = roles.campus_admin as Record<string, unknown>;
    expect(ca.campus_scoped).toBe(true);
  });
});

// --- Golden fixture references ---

describe("fixture-verified role data", () => {
  const roles = loadRoles(REPO_ROOT);

  it("visitor role data matches fixture 1 scope expectations", () => {
    const v = roles.visitor as Record<string, unknown>;
    expect(v.allowed_visibility).toEqual(["public"]);
    expect(v.allowed_data_levels).toEqual(["L1"]);
  });

  it("parent role data matches fixture 2 scope expectations", () => {
    const p = roles.parent as Record<string, unknown>;
    expect(p.allowed_visibility).toEqual(["public", "protected"]);
    expect(p.allowed_data_levels).toEqual(["L1", "L2"]);
  });

  it("sales role data matches fixture 3 scope expectations", () => {
    const s = roles.sales as Record<string, unknown>;
    expect(s.allowed_visibility).toEqual(["public", "protected", "internal"]);
    expect(s.allowed_data_levels).toEqual(["L1", "L2", "L3"]);
  });
});
