export interface RecommendationInput {
  profile: Record<string, unknown>;
  allowed_evidence: Record<string, unknown>[];
  campus: string | null;
  role: string;
  consultation_stage: string;
}

export const DEFAULT_RECOMMENDATION_INPUT: Omit<RecommendationInput, "profile" | "allowed_evidence"> = {
  campus: null,
  role: "parent",
  consultation_stage: "NEEDS_ASSESSMENT",
};

export interface ClassRecommendation {
  recommended_class_type: string | null;
  confidence: string;
  reasons: string[];
  not_suitable_if: string[];
  missing_info: string[];
  next_questions: string[];
  risk_warnings: string[];
  evidence_ids: string[];
}

export function createClassRecommendation(
  overrides: Partial<ClassRecommendation> = {},
): ClassRecommendation {
  return {
    recommended_class_type: null,
    confidence: "low",
    reasons: [],
    not_suitable_if: [],
    missing_info: [],
    next_questions: [],
    risk_warnings: [],
    evidence_ids: [],
    ...overrides,
  };
}
