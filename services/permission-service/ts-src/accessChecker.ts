export type AccessResult = [boolean, string];

function toDateStr(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function canAccess(
  item: Record<string, unknown>,
  scope: Record<string, unknown>,
  today?: Date,
): AccessResult {
  const now = today ?? new Date();
  const todayStr = toDateStr(now);

  if (item.review_status !== "approved") {
    return [false, "not_approved"];
  }

  const allowedVis = (scope.allowed_visibility as string[] | undefined) ?? [];
  if (!allowedVis.includes(item.visibility as string)) {
    return [false, "visibility_denied"];
  }

  const allowedDL = (scope.allowed_data_levels as string[] | undefined) ?? [];
  if (!allowedDL.includes(item.data_level as string)) {
    return [false, "data_level_denied"];
  }

  const itemRoles = (item.allowed_roles as string[] | undefined) ?? [];
  if (!itemRoles.includes(scope.role as string)) {
    return [false, "role_denied"];
  }

  const campuses = (item.campus_scope as string[] | undefined) ?? [];
  if (!campuses.includes("all") && !campuses.includes(scope.campus as string)) {
    return [false, "campus_denied"];
  }

  const itemTags = (item.business_tags as string[] | undefined) ?? [];
  const forbiddenTags = (scope.forbidden_tags as string[] | undefined) ?? [];
  for (const t of itemTags) {
    if (forbiddenTags.includes(t)) return [false, "forbidden_tag"];
  }

  const effRaw = item.effective_date;
  const effStr = effRaw === undefined ? "0000-01-01" : String(effRaw);
  if (effStr > todayStr) return [false, "not_effective"];

  const expRaw = item.expiry_date;
  const expStr = expRaw === undefined ? "9999-12-31" : String(expRaw);
  if (expStr < todayStr) return [false, "expired"];

  return [true, "allowed"];
}
