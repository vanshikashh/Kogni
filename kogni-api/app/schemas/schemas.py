from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Feature vector ───────────────────────────────────────────────────────────

class FeatureVectorIn(BaseModel):
    ts: Optional[int] = None              # epoch ms from client (optional)
    window_duration_s: Optional[int] = 30

    # Keystroke
    iki_mean: Optional[float] = None
    iki_std: Optional[float] = None
    hold_mean: Optional[float] = None
    error_rate: Optional[float] = None
    key_count: Optional[int] = 0

    # Scroll
    scroll_velocity: Optional[float] = None
    direction_reversals: Optional[int] = 0
    scroll_event_count: Optional[int] = 0

    # Context
    tab_switches: Optional[int] = 0
    hour_of_day: Optional[int] = None
    day_of_week: Optional[int] = None


class IngestRequest(BaseModel):
    vectors: list[FeatureVectorIn]


class IngestResponse(BaseModel):
    accepted: int
    fatigue_score: Optional[float] = None   # latest score if available


# ─── Dashboard ────────────────────────────────────────────────────────────────

class DailyScoreOut(BaseModel):
    date: datetime
    fatigue_score: Optional[float]
    trajectory_score: Optional[float]
    shap_feature_1: Optional[str]
    shap_value_1: Optional[float]
    shap_feature_2: Optional[str]
    shap_value_2: Optional[float]
    shap_feature_3: Optional[str]
    shap_value_3: Optional[float]

    class Config:
        from_attributes = True


class WeeklyReportResponse(BaseModel):
    scores: list[DailyScoreOut]
    avg_fatigue: Optional[float]
    trend_direction: str   # "improving" | "declining" | "stable"
