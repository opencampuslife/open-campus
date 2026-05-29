const ZERO_WIDTH_RE = /[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff]/gu;
const WHITESPACE_COLLAPSE_RE = /\s+/gu;

const INJECTION_PATTERNS = [
  "忽略以上",
  "忽略之前",
  "ignore previous",
  "ignore above",
  "system prompt",
  "developer message",
  "越权",
  "绕过",
];

const EXTERNAL_ROLES = new Set(["visitor", "student", "parent"]);

const REQUIRED_EVIDENCE_FIELDS = new Set([
  "chunk_id",
  "doc_id",
  "title",
  "content",
  "visibility",
  "data_level",
  "allowed_roles",
  "source_uri",
]);

function normalize(text: string): string {
  text = text.replace(ZERO_WIDTH_RE, "");
  text = text.replace(WHITESPACE_COLLAPSE_RE, " ");
  return text.toLowerCase().trim();
}

function pyStr(val: unknown): string {
  if (val === null) return "None";
  if (Array.isArray(val)) return JSON.stringify(val);
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

export function validateLlmRequest(
  request: Record<string, unknown>,
): { valid: boolean; violations: string[] } {
  const violations: string[] = [];

  const message = pyStr(request.message ?? "");
  const evidence = pyStr(request.evidence ?? "");
  const joined = `${message}\n${evidence}`;
  const normalized = normalize(joined);

  for (const pattern of INJECTION_PATTERNS) {
    if (normalized.includes(pattern.toLowerCase())) {
      violations.push(`prompt_injection_pattern:${pattern}`);
    }
  }

  const scope = (request.scope ?? {}) as Record<string, unknown>;
  const evidenceList = Array.isArray(request.evidence) ? request.evidence : [];

  for (const chunk of evidenceList) {
    const chunkRecord = chunk as Record<string, unknown>;
    const missing: string[] = [];
    for (const field of REQUIRED_EVIDENCE_FIELDS) {
      if (!(field in chunkRecord)) {
        missing.push(field);
      }
    }
    if (missing.length > 0) {
      violations.push(`evidence_missing_fields:${missing.sort().join(",")}`);
    }
  }

  const role = "role" in scope ? String(scope.role) : undefined;
  if (role && EXTERNAL_ROLES.has(role)) {
    for (const chunk of evidenceList) {
      const ch = chunk as Record<string, unknown>;
      if (ch.visibility === "internal" || ch.data_level === "L3" || ch.data_level === "L4") {
        violations.push("external_request_contains_internal_evidence");
        break;
      }
    }
  }

  return { valid: violations.length === 0, violations };
}
