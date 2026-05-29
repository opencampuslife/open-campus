import type { ClassRecommendation } from "./recommendationModel.js";

function noRecommendationMessage(
  rec: ClassRecommendation,
  identityType: string,
): string {
  const lines: string[] = ["目前信息还不够充分，暂时无法给出具体的班型建议。"];

  if (rec.next_questions.length > 0) {
    lines.push("\n为了帮你判断合适的班型，我还需要了解以下信息：");
    for (const q of rec.next_questions.slice(0, 2)) {
      lines.push(`- ${q}`);
    }
  }

  if (rec.risk_warnings.length > 0) {
    lines.push("\n注意：");
    for (const w of rec.risk_warnings) {
      lines.push(`- ${w}`);
    }
  }

  return lines.join("\n");
}

export function explainRecommendation(
  rec: ClassRecommendation,
  identityType: string = "parent",
): string {
  if (rec.recommended_class_type === null) {
    return noRecommendationMessage(rec, identityType);
  }

  const parts: string[] = [];
  parts.push(
    `根据${identityType === "parent" ? "您目前" : "目前"}提供的信息，建议优先了解「${rec.recommended_class_type}」。`,
  );

  if (rec.reasons.length > 0) {
    parts.push("\n主要原因：");
    for (const r of rec.reasons.slice(0, 3)) {
      parts.push(`- ${r}`);
    }
  }

  if (rec.not_suitable_if.length > 0) {
    parts.push(
      `\n但需要注意，如果${identityType === "parent" ? "孩子" : "你"}有以下情况，这个班型不一定是最合适的：`,
    );
    for (const ns of rec.not_suitable_if) {
      parts.push(`- ${ns}`);
    }
  }

  if (rec.missing_info.length > 0 && rec.next_questions.length > 0) {
    parts.push("\n为了做出更准确的判断，我还需要了解：");
    for (const q of rec.next_questions.slice(0, 2)) {
      parts.push(`- ${q}`);
    }
  }

  if (rec.risk_warnings.length > 0) {
    parts.push("\n温馨提示：");
    for (const w of rec.risk_warnings) {
      parts.push(`- ${w}`);
    }
  }

  return parts.join("\n");
}
