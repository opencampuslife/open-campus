import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { buildScope } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "permission_service.json");

interface ScopeFixture {
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

const fixtures: ScopeFixture[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as ScopeFixture[];

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

function runPythonBuildScope(
  identity: Record<string, unknown>,
): Record<string, unknown> {
  const tmpScript = resolve(tmpdir(), `scope_${randomUUID()}.py`);
  const script = [
    "import json, sys, pathlib",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "knowledge-service", "src"))})`,
    "from scope_builder import build_scope",
    `identity = json.loads(${JSON.stringify(JSON.stringify(identity))})`,
    `result = build_scope(identity, pathlib.Path(${JSON.stringify(REPO_ROOT)}))`,
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

function identityFor(role: string, overrides?: Record<string, unknown>): Record<string, unknown> {
  return {
    user_id: `u_${role}`,
    role,
    campus: "all",
    auth_level: "authenticated",
    ...overrides,
  };
}

// --- Golden Fixture Parity (first 4 scope fixtures) ---

describe("golden fixture parity", () => {
  it("fixture 0: visitor scope matches stored golden JSON", () => {
    const tsOut = buildScope(fixtures[0]!.input as Record<string, unknown>, REPO_ROOT);
    expect(deepEqual(tsOut, fixtures[0]!.output)).toBe(true);
  });

  it("fixture 1: parent scope matches golden JSON", () => {
    const tsOut = buildScope(fixtures[1]!.input as Record<string, unknown>, REPO_ROOT);
    expect(deepEqual(tsOut, fixtures[1]!.output)).toBe(true);
  });

  it("fixture 2: sales scope matches golden JSON", () => {
    const tsOut = buildScope(fixtures[2]!.input as Record<string, unknown>, REPO_ROOT);
    expect(deepEqual(tsOut, fixtures[2]!.output)).toBe(true);
  });

  it("fixture 3: unknown role throws ValueError", () => {
    expect(() =>
      buildScope(fixtures[3]!.input as Record<string, unknown>, REPO_ROOT),
    ).toThrow("Unknown role: super_admin");
  });

  it("fixture 4: student scope matches golden JSON", () => {
    const tsOut = buildScope(fixtures[4]!.input as Record<string, unknown>, REPO_ROOT);
    expect(deepEqual(tsOut, fixtures[4]!.output)).toBe(true);
  });

  it("visitor scope matches live Python build_scope", () => {
    const id = fixtures[0]!.input as Record<string, unknown>;
    const tsOut = buildScope(id, REPO_ROOT);
    const pyOut = runPythonBuildScope(id);
    expect(deepEqual(tsOut, pyOut)).toBe(true);
  });

  it("parent scope matches live Python build_scope", () => {
    const id = fixtures[1]!.input as Record<string, unknown>;
    const tsOut = buildScope(id, REPO_ROOT);
    const pyOut = runPythonBuildScope(id);
    expect(deepEqual(tsOut, pyOut)).toBe(true);
  });

  it("sales scope matches live Python build_scope", () => {
    const id = fixtures[2]!.input as Record<string, unknown>;
    const tsOut = buildScope(id, REPO_ROOT);
    const pyOut = runPythonBuildScope(id);
    expect(deepEqual(tsOut, pyOut)).toBe(true);
  });

  it("student scope matches live Python build_scope", () => {
    const id = fixtures[4]!.input as Record<string, unknown>;
    const tsOut = buildScope(id, REPO_ROOT);
    const pyOut = runPythonBuildScope(id);
    expect(deepEqual(tsOut, pyOut)).toBe(true);
  });
});

// --- A: Scope Output Snapshot (9 roles) ---

describe("A: scope output snapshot", () => {
  it("visitor scope", () => {
    const scope = buildScope(identityFor("visitor"), REPO_ROOT);
    expect(scope.role).toBe("visitor");
    expect(scope.allowed_visibility).toEqual(["public"]);
    expect(scope.allowed_data_levels).toEqual(["L1"]);
    expect(scope.allowed_roles).toEqual(["visitor", "student", "parent", "customer"]);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("customer scope", () => {
    const scope = buildScope(identityFor("customer"), REPO_ROOT);
    expect(scope.role).toBe("customer");
    expect(scope.allowed_visibility).toEqual(["public", "protected"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2"]);
    expect(scope.allowed_roles).toEqual(["visitor", "student", "parent", "customer"]);
    // customer NOT in DEFAULT_FORBIDDEN_TAGS, YAML has no forbidden_tags → []
    expect(scope.forbidden_tags).toEqual([]);
  });

  it("student scope", () => {
    const scope = buildScope(identityFor("student"), REPO_ROOT);
    expect(scope.role).toBe("student");
    expect(scope.allowed_visibility).toEqual(["public", "protected"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2"]);
    expect(scope.allowed_roles).toEqual(["visitor", "student", "parent", "customer"]);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("parent scope", () => {
    const scope = buildScope(identityFor("parent"), REPO_ROOT);
    expect(scope.role).toBe("parent");
    expect(scope.allowed_visibility).toEqual(["public", "protected"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2"]);
    expect(scope.allowed_roles).toEqual(["visitor", "student", "parent", "customer"]);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("sales scope", () => {
    const scope = buildScope(identityFor("sales"), REPO_ROOT);
    expect(scope.role).toBe("sales");
    expect(scope.allowed_visibility).toEqual(["public", "protected", "internal"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2", "L3"]);
    expect(scope.allowed_roles).toEqual(["visitor", "student", "parent", "sales"]);
    // sales has no forbidden_tags in YAML and NOT in DEFAULT_FORBIDDEN_TAGS → []
    expect(scope.forbidden_tags).toEqual([]);
  });

  it("teacher scope", () => {
    const scope = buildScope(identityFor("teacher"), REPO_ROOT);
    expect(scope.role).toBe("teacher");
    expect(scope.allowed_visibility).toEqual(["public", "protected"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2"]);
    expect(scope.allowed_roles).toEqual(["teacher"]);
    expect(scope.forbidden_tags).toEqual(["crm_rule", "deal_info", "internal_pricing"]);
  });

  it("operator scope", () => {
    const scope = buildScope(identityFor("operator"), REPO_ROOT);
    expect(scope.role).toBe("operator");
    expect(scope.allowed_visibility).toEqual(["public", "protected", "internal"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2", "L3"]);
    expect(scope.allowed_roles).toEqual(["operator"]);
    expect(scope.forbidden_tags).toEqual(["student_private_case"]);
  });

  it("campus_admin scope", () => {
    const scope = buildScope(identityFor("campus_admin"), REPO_ROOT);
    expect(scope.role).toBe("campus_admin");
    expect(scope.allowed_visibility).toEqual(["public", "protected", "internal"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2", "L3"]);
    expect(scope.allowed_roles).toEqual(["campus_admin"]);
    expect(scope.forbidden_tags).toEqual([]);
  });

  it("admin scope", () => {
    const scope = buildScope(identityFor("admin"), REPO_ROOT);
    expect(scope.role).toBe("admin");
    expect(scope.allowed_visibility).toEqual(["public", "protected", "internal", "admin"]);
    expect(scope.allowed_data_levels).toEqual(["L1", "L2", "L3", "L4"]);
    expect(scope.allowed_roles).toEqual(["admin"]);
    expect(scope.forbidden_tags).toEqual([]);
  });

  it("all 9 scopes match Python build_scope output", () => {
    const roles = ["visitor", "customer", "student", "parent", "sales",
                   "teacher", "operator", "campus_admin", "admin"];
    for (const role of roles) {
      const id = identityFor(role);
      const tsOut = buildScope(id, REPO_ROOT);
      const pyOut = runPythonBuildScope(id);
      expect(deepEqual(tsOut, pyOut)).toBe(true);
    }
  });
});

// --- B: Default Behavior Snapshot ---

describe("B: default behavior snapshot", () => {
  it("campus defaults to 'all' when identity has no campus", () => {
    const id = identityFor("visitor", { campus: undefined });
    delete id.campus;
    const scope = buildScope(id, REPO_ROOT);
    expect(scope.campus).toBe("all");
  });

  it("campus preserves identity value when present", () => {
    const scope = buildScope(identityFor("visitor", { campus: "bj-campus" }), REPO_ROOT);
    expect(scope.campus).toBe("bj-campus");
  });

  it("auth_level defaults to 'anonymous' when identity has none", () => {
    const id = identityFor("visitor", { auth_level: undefined });
    delete id.auth_level;
    const scope = buildScope(id, REPO_ROOT);
    expect(scope.auth_level).toBe("anonymous");
  });

  it("auth_level preserves identity value when present", () => {
    const scope = buildScope(identityFor("visitor", { auth_level: "admin" }), REPO_ROOT);
    expect(scope.auth_level).toBe("admin");
  });

  it("user_id is null when identity has no user_id", () => {
    const id = identityFor("visitor", { user_id: undefined });
    delete id.user_id;
    const scope = buildScope(id, REPO_ROOT);
    expect(scope.user_id).toBeNull();
  });

  it("user_id preserves identity value when present", () => {
    const scope = buildScope(identityFor("visitor", { user_id: "custom-1" }), REPO_ROOT);
    expect(scope.user_id).toBe("custom-1");
  });

  it("unknown role throws correct error", () => {
    expect(() =>
      buildScope(identityFor("super_admin"), REPO_ROOT),
    ).toThrow("Unknown role: super_admin");
  });

  it("Python also throws for unknown role", () => {
    const tmpScript = resolve(tmpdir(), `scope_err_${randomUUID()}.py`);
    const id = identityFor("super_admin");
    const script = [
      "import sys, pathlib, json",
      `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "permission-service", "src"))})`,
      `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "knowledge-service", "src"))})`,
      "from scope_builder import build_scope",
      `identity = json.loads(${JSON.stringify(JSON.stringify(id))})`,
      `build_scope(identity, pathlib.Path(${JSON.stringify(REPO_ROOT)}))`,
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

  it("repeatable calls produce identical scope", () => {
    const a = buildScope(identityFor("admin"), REPO_ROOT);
    const b = buildScope(identityFor("admin"), REPO_ROOT);
    expect(deepEqual(a, b)).toBe(true);
  });
});

// --- C: Non-Decision Boundary Snapshot ---

describe("C: non-decision boundary snapshot", () => {
  it("scopeBuilder does not import metadataFilter or accessChecker", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "scopeBuilder.ts"),
      "utf-8",
    );
    expect(source).not.toContain("canAccess");
    expect(source).not.toContain("filterAllowed");
    expect(source).not.toContain("access_checker");
    expect(source).not.toContain("metadataFilter");
  });

  it("buildScope returns scope, not allow/deny decision", () => {
    const scope = buildScope(identityFor("visitor"), REPO_ROOT);
    const keys = Object.keys(scope).sort();
    expect(keys).toEqual([
      "allowed_data_levels",
      "allowed_roles",
      "allowed_visibility",
      "auth_level",
      "campus",
      "forbidden_tags",
      "role",
      "user_id",
    ]);
    expect(scope).not.toHaveProperty("passed");
    expect(scope).not.toHaveProperty("violations");
    expect(scope).not.toHaveProperty("reason");
  });
});

// --- Order stability ---

describe("array order stability", () => {
  it("allowed_visibility order matches YAML definition", () => {
    const s = buildScope(identityFor("admin"), REPO_ROOT);
    expect(s.allowed_visibility).toEqual(["public", "protected", "internal", "admin"]);
  });

  it("allowed_data_levels order matches YAML definition", () => {
    const s = buildScope(identityFor("admin"), REPO_ROOT);
    expect(s.allowed_data_levels).toEqual(["L1", "L2", "L3", "L4"]);
  });

  it("allowed_roles order is stable", () => {
    const s = buildScope(identityFor("visitor"), REPO_ROOT);
    expect(s.allowed_roles).toEqual(["visitor", "student", "parent", "customer"]);
  });

  it("forbidden_tags order matches policy definition", () => {
    const s = buildScope(identityFor("teacher"), REPO_ROOT);
    expect(s.forbidden_tags).toEqual(["crm_rule", "deal_info", "internal_pricing"]);
  });
});

// --- Default forbidden_tags edge cases ---

describe("forbidden_tags default behavior", () => {
  it("visitor gets DEFAULT_FORBIDDEN_TAGS", () => {
    const scope = buildScope(identityFor("visitor"), REPO_ROOT);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("student gets DEFAULT_FORBIDDEN_TAGS", () => {
    const scope = buildScope(identityFor("student"), REPO_ROOT);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("parent gets DEFAULT_FORBIDDEN_TAGS", () => {
    const scope = buildScope(identityFor("parent"), REPO_ROOT);
    expect(scope.forbidden_tags).toEqual(["internal_pricing", "sales_script", "crm_rule"]);
  });

  it("customer has no forbidden_tags (not in DEFAULT, not in YAML) → empty array", () => {
    const scope = buildScope(identityFor("customer"), REPO_ROOT);
    expect(scope.forbidden_tags).toEqual([]);
  });

  it("sales has no forbidden_tags (not in DEFAULT, not in YAML) → empty array", () => {
    const scope = buildScope(identityFor("sales"), REPO_ROOT);
    expect(scope.forbidden_tags).toEqual([]);
  });
});
