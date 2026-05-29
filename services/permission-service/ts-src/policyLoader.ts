import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse } from "yaml";

function loadYaml(projectRoot: string, relativePath: string): Record<string, unknown> {
  const fullPath = resolve(projectRoot, relativePath);
  const raw = readFileSync(fullPath, "utf-8");
  return parse(raw) as Record<string, unknown>;
}

export function loadRoles(projectRoot: string): Record<string, unknown> {
  const parsed = loadYaml(projectRoot, "configs/roles.yaml");
  return parsed.roles as Record<string, unknown>;
}

export function loadDataLevels(projectRoot: string): Record<string, unknown> {
  const parsed = loadYaml(projectRoot, "configs/data_levels.yaml");
  return parsed.data_levels as Record<string, unknown>;
}

export function loadRetrievalPolicy(projectRoot: string): Record<string, unknown> {
  return loadYaml(projectRoot, "configs/retrieval_policy.yaml");
}

export function loadAllPolicies(projectRoot: string): {
  roles: Record<string, unknown>;
  dataLevels: Record<string, unknown>;
  retrievalPolicy: Record<string, unknown>;
} {
  return {
    roles: loadRoles(projectRoot),
    dataLevels: loadDataLevels(projectRoot),
    retrievalPolicy: loadRetrievalPolicy(projectRoot),
  };
}
