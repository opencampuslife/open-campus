import {
  type RecommendationInput,
  type ClassRecommendation,
  DEFAULT_RECOMMENDATION_INPUT,
} from "./recommendationModel.js";
import { recommend } from "./classRules.js";

const NEEDED_PROFILE_KEYS = [
  "current_score",
  "subject_type",
  "target_school_level",
  "weak_subjects",
  "self_discipline_level",
  "budget_range",
  "preferred_campus",
  "boarding_preference",
] as const;

export function generateRecommendation(
  profile: Record<string, unknown>,
  allowedEvidence: Record<string, unknown>[],
  campus?: string | null,
  role?: string,
  consultationStage?: string,
): ClassRecommendation {
  const input: RecommendationInput = {
    profile,
    allowed_evidence: allowedEvidence,
    campus: campus ?? DEFAULT_RECOMMENDATION_INPUT.campus,
    role: role ?? DEFAULT_RECOMMENDATION_INPUT.role,
    consultation_stage: consultationStage ?? DEFAULT_RECOMMENDATION_INPUT.consultation_stage,
  };

  const rec = recommend(input.profile, input.allowed_evidence);

  const knownKeys = new Set(Object.keys(profile));
  for (const key of NEEDED_PROFILE_KEYS) {
    if (!knownKeys.has(key) || !profile[key]) {
      if (!rec.missing_info.includes(key)) {
        rec.missing_info.push(key);
      }
    }
  }

  return rec;
}
