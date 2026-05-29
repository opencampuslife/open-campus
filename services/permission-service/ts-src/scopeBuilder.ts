import { loadRoles } from "./policyLoader.js";

const DEFAULT_FORBIDDEN_TAGS: Record<string, string[]> = {
  visitor: ["internal_pricing", "sales_script", "crm_rule"],
  student: ["internal_pricing", "sales_script", "crm_rule"],
  parent: ["internal_pricing", "sales_script", "crm_rule"],
};

function allowedRolesFor(role: string): string[] {
  if (["visitor", "student", "parent", "customer"].includes(role)) {
    return ["visitor", "student", "parent", "customer"];
  }
  if (role === "sales") {
    return ["visitor", "student", "parent", "sales"];
  }
  return [role];
}

export function buildScope(
  identity: Record<string, unknown>,
  projectRoot: string,
): Record<string, unknown> {
  const roles = loadRoles(projectRoot);
  const role = identity.role as string;
  const policy = roles[role] as Record<string, unknown> | undefined;
  if (!policy) {
    throw new Error(`Unknown role: ${role}`);
  }

  return {
    user_id: identity.user_id ?? null,
    role,
    campus: (identity.campus as string) ?? "all",
    auth_level: (identity.auth_level as string) ?? "anonymous",
    allowed_visibility: (policy.allowed_visibility as string[] | undefined) ?? [],
    allowed_data_levels: (policy.allowed_data_levels as string[] | undefined) ?? [],
    allowed_roles: allowedRolesFor(role),
    forbidden_tags:
      (policy.forbidden_tags as string[] | undefined) ??
      DEFAULT_FORBIDDEN_TAGS[role] ??
      [],
  };
}
