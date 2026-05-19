export interface ShapDriver {
  feature: string;
  label: string;
  shap_value: number;
  direction: "increases_fatigue" | "reduces_fatigue";
}

export interface DailyScore {
  date: string;
  fatigue_score: number | null;
  trajectory_score: number | null;
  shap_feature_1: string | null;
  shap_value_1: number | null;
  shap_feature_2: string | null;
  shap_value_2: number | null;
  shap_feature_3: string | null;
  shap_value_3: number | null;
}

export interface WeeklyReport {
  scores: DailyScore[];
  avg_fatigue: number | null;
  trend_direction: "improving" | "declining" | "stable";
}

export interface LiveScore {
  user_id: number;
  fatigue_score: number;
  status: "nominal" | "moderate" | "high";
  shap_top3: ShapDriver[];
  ts: string;
  type?: "recovery_intervention";
  message?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export type FatigueStatus = "nominal" | "moderate" | "high";
