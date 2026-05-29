import {
  createClassRecommendation,
  type ClassRecommendation,
} from "./recommendationModel.js";

function missingFromProfile(profile: Record<string, unknown>, fields: string[]): string[] {
  const missing: string[] = [];
  for (const f of fields) {
    const val = profile[f];
    if (!val || val === "" || val === 0 || (Array.isArray(val) && val.length === 0)) {
      missing.push(f);
    }
  }
  return missing;
}

function pickEvidenceIds(evidence: Record<string, unknown>[], keywords: string[]): string[] {
  return evidence
    .filter((e) => {
      const content = String(e["content"] ?? "").toLowerCase();
      return keywords.some((kw) => content.includes(kw));
    })
    .map((e) => String(e["chunk_id"] ?? ""))
    .slice(0, 3);
}

function smallClassRule(
  profile: Record<string, unknown>,
  evidence: Record<string, unknown>[],
): ClassRecommendation | null {
  const score = Number(profile["current_score"] ?? 0);
  const weak = (profile["weak_subjects"] as string[]) ?? [];
  const discipline = String(profile["self_discipline_level"] ?? "");
  const target = String(profile["target_school_level"] ?? "");

  if (score >= 350 && weak.length >= 2 && (discipline === "medium" || discipline === "low")) {
    const evidenceIds = pickEvidenceIds(evidence, ["小班", "强化", "分层", "管理"]);
    return createClassRecommendation({
      recommended_class_type: "小班强化班",
      confidence: "medium",
      reasons: [
        `当前分数${score}分，目标为${target || "本科"}，存在提升空间`,
        `检测到${weak.length}个薄弱科目：${weak.join("、")}`,
        `自律水平为${discipline === "low" ? "中等偏低" : "中等"}，需要稳定管理与反馈`,
      ],
      not_suitable_if: ["学生自律性极强且只需单科补弱", "预算明显低于该班型区间"],
      missing_info: missingFromProfile(profile, ["budget_range", "preferred_campus", "boarding_preference"]),
      next_questions: ["孩子更倾向走读还是住宿？", "预算方面有什么考虑？"],
      risk_warnings: ["不承诺提分幅度，最终录取以高考实际表现为准"],
      evidence_ids: evidenceIds,
    });
  }
  return null;
}

function closedBoardingRule(
  profile: Record<string, unknown>,
  evidence: Record<string, unknown>[],
): ClassRecommendation | null {
  const discipline = String(profile["self_discipline_level"] ?? "");
  const concerns = profile["parent_concerns"];
  const boarding = String(profile["boarding_preference"] ?? "");
  const score = Number(profile["current_score"] ?? 0);

  const conditions =
    discipline === "low" ||
    String(concerns ?? "").includes("管理") ||
    boarding === "boarding";

  if (conditions && score >= 300) {
    const evidenceIds = pickEvidenceIds(evidence, ["封闭", "全日制", "住宿", "管理"]);
    return createClassRecommendation({
      recommended_class_type: "全日制封闭班",
      confidence: "medium",
      reasons: [
        "自律性较低或家长关注管理",
        "需要封闭式学习环境以确保学习纪律",
        "适合需要全天候管理支持的学生",
      ],
      not_suitable_if: ["学生不住校且家庭可提供稳定监督", "走读需求明确"],
      missing_info: missingFromProfile(profile, ["preferred_campus", "budget_range"]),
      next_questions: ["是否接受住宿式管理？", "离哪个校区比较方便？"],
      risk_warnings: ["封闭式环境适应期是个体化的，建议试听确认"],
      evidence_ids: evidenceIds,
    });
  }
  return null;
}

function singleSubjectRule(
  profile: Record<string, unknown>,
  evidence: Record<string, unknown>[],
): ClassRecommendation | null {
  const weak = (profile["weak_subjects"] as string[]) ?? [];
  const discipline = String(profile["self_discipline_level"] ?? "");
  const score = Number(profile["current_score"] ?? 0);

  if (weak.length === 1 && (discipline === "high" || discipline === "medium") && score >= 380) {
    const evidenceIds = pickEvidenceIds(evidence, ["单科", "专项", "突破", "一对一"]);
    return createClassRecommendation({
      recommended_class_type: "单科突破班",
      confidence: "medium",
      reasons: [
        `只有一个主要薄弱科目：${weak[0]}`,
        `自律水平${discipline === "high" ? "较高" : "中等"}，可独立完成大部分学习`,
        "总分相对稳定，建议集中突破薄弱科目",
      ],
      not_suitable_if: ["多科薄弱（≥2科）", "自律性明显偏低"],
      missing_info: missingFromProfile(profile, ["target_school_level"]),
      next_questions: [`对于${weak[0]}，目前主要问题是基础不牢还是解题技巧？`],
      risk_warnings: ["单科突破通常需要配合整体学习节奏，建议先做学情诊断"],
      evidence_ids: evidenceIds,
    });
  }
  return null;
}

function sprintClassRule(
  profile: Record<string, unknown>,
  evidence: Record<string, unknown>[],
): ClassRecommendation | null {
  const score = Number(profile["current_score"] ?? 0);
  const targetScore = Number(profile["target_score"] ?? 0);

  if (targetScore > 0 && Math.abs(targetScore - score) <= 40) {
    const evidenceIds = pickEvidenceIds(evidence, ["冲刺", "应试", "真题", "技巧"]);
    return createClassRecommendation({
      recommended_class_type: "冲刺班",
      confidence: "medium",
      reasons: [
        `当前${score}分，目标${targetScore}分，差距适中`,
        "距离考试较近，侧重查漏补缺和应试技巧",
        "适合有明确目标且基础较好的学生",
      ],
      not_suitable_if: ["基础差距过大（≥80分）", "需要长期系统补课"],
      missing_info: missingFromProfile(profile, ["weak_subjects", "exam_year"]),
      next_questions: ["距离高考还有多少时间？", "主要想加强哪些题型的训练？"],
      risk_warnings: ["冲刺班以提分效率为导向，需要学生已有较强基础"],
      evidence_ids: evidenceIds,
    });
  }
  return null;
}

function noRecommendation(profile: Record<string, unknown>): ClassRecommendation {
  const missing = missingFromProfile(profile, ["current_score", "subject_type", "target_school_level"]);
  const identityType = String(profile["identity_type"] ?? "");
  return createClassRecommendation({
    recommended_class_type: null,
    confidence: "low",
    reasons: ["当前画像信息不足以做出班型推荐"],
    missing_info: missing,
    next_questions: [
      `请问${identityType === "parent" ? "您的" : ""}孩子是物理类还是历史类？`,
      "目前考试成绩大概在多少分？",
    ],
    risk_warnings: ["信息不足时不做班型推荐，以免误导"],
    evidence_ids: [],
  });
}

export function recommend(
  profile: Record<string, unknown>,
  evidence: Record<string, unknown>[],
): ClassRecommendation {
  const rules = [smallClassRule, closedBoardingRule, singleSubjectRule, sprintClassRule];
  for (const rule of rules) {
    const result = rule(profile, evidence);
    if (result) return result;
  }
  return noRecommendation(profile);
}
