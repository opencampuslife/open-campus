import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse } from "yaml";

const EXTERNAL_ROLES = new Set(["visitor", "student", "parent"]);
const PHONE_PATTERN = /1[3-9]\d{9}/;

export interface ComplianceResult {
  passed: boolean;
  violations: string[];
  rewrite_guidance: string[];
}

export function evaluateAnswer(
  answer: string,
  scope: Record<string, unknown>,
  projectRoot: string,
): ComplianceResult {
  const rulesPath = resolve(projectRoot, "configs", "compliance_rules.yaml");
  const raw = readFileSync(rulesPath, "utf-8");
  const rules = parse(raw) as Record<string, unknown>;
  const role = (scope.role as string | undefined) ?? "visitor";
  const externalRole = EXTERNAL_ROLES.has(role);
  const violations: string[] = [];

  const rawBlocked = (rules.blocked_phrases ?? []) as string[];
  const blockedPhrases: string[] = [...rawBlocked];
  if (!externalRole) {
    const filtered = blockedPhrases.filter(
      (p) => p !== "优惠底价" && p !== "内部名额",
    );
    violations.push(...filtered.filter((p) => answer.includes(p)));
  } else {
    violations.push(...blockedPhrases.filter((p) => answer.includes(p)));
  }

  if (externalRole) {
    const leakTerms = ["内部参考", "内部规则", "内部话术", "内部优惠"];
    if (leakTerms.some((t) => answer.includes(t))) {
      violations.push("internal_reference_leak");
    }
  }

  if (PHONE_PATTERN.test(answer)) {
    violations.push("privacy_phone_number");
  }

  if (answer.includes("100%") || answer.includes("一定会")) {
    violations.push("absolute_claim");
  }

  const guidance = buildGuidance(violations, rules);
  return {
    passed: violations.length === 0,
    violations,
    rewrite_guidance: guidance,
  };
}

function buildGuidance(
  violations: string[],
  rules: Record<string, unknown>,
): string[] {
  const guidanceMap = (rules.rewrite_guidance ?? {}) as Record<string, unknown>;
  const guidance: string[] = [];

  const promiseViolations = new Set(["保证录取", "保证提分", "absolute_claim"]);
  if (violations.some((v) => promiseViolations.has(v))) {
    guidance.push(String(guidanceMap.promise_risk ?? ""));
  }

  const pricingViolations = new Set(["优惠底价", "internal_reference_leak"]);
  if (violations.some((v) => pricingViolations.has(v))) {
    guidance.push(String(guidanceMap.pricing_risk ?? ""));
  }

  if (violations.includes("privacy_phone_number")) {
    guidance.push(String(guidanceMap.privacy_risk ?? ""));
  }

  return guidance.filter((item) => item !== "");
}

export function rewriteAnswer(answer: string, violations: string[]): string {
  if (violations.includes("privacy_phone_number")) {
    return (
      "这个问题涉及个人隐私信息，当前不能直接展示联系方式或学生识别信息。" +
      "建议由顾问在授权场景下继续跟进。"
    );
  }

  if (violations.includes("internal_reference_leak") || violations.includes("优惠底价")) {
    return (
      "这个问题需要按学校正式口径处理，不能透露未公开的优惠、内部规则或内部参考内容。" +
      "可以先根据学生基础、目标、薄弱科目和意向校区做评估，再由顾问提供合规说明。"
    );
  }

  return (
    "这个问题需要按学校正式口径处理，不能承诺固定提分、保证录取，" +
    "也不能透露未公开的优惠或内部规则。可以先根据学生基础、目标、薄弱科目和意向校区做评估，" +
    "再由顾问提供合规说明。"
  );
}

export function evaluateAndRewrite(
  answer: string,
  scope: Record<string, unknown>,
  projectRoot: string,
): ComplianceResult & { rewritten_answer: string } {
  const result = evaluateAnswer(answer, scope, projectRoot);
  return {
    ...result,
    rewritten_answer: result.passed ? answer : rewriteAnswer(answer, result.violations),
  };
}
