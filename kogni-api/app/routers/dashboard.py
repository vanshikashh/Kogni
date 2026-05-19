from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.event import DailyScore
from app.schemas.schemas import WeeklyReportResponse, DailyScoreOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/weekly-report", response_model=WeeklyReportResponse)
def weekly_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=7)

    scores = (
        db.query(DailyScore)
        .filter(DailyScore.user_id == current_user.id, DailyScore.date >= since)
        .order_by(DailyScore.date.asc())
        .all()
    )

    if not scores:
        return WeeklyReportResponse(scores=[], avg_fatigue=None, trend_direction="stable")

    fatigue_values = [s.fatigue_score for s in scores if s.fatigue_score is not None]
    avg = round(sum(fatigue_values) / len(fatigue_values), 4) if fatigue_values else None

    # Trend: compare first half avg vs second half avg
    trend = "stable"
    if len(fatigue_values) >= 4:
        mid = len(fatigue_values) // 2
        first_half = sum(fatigue_values[:mid]) / mid
        second_half = sum(fatigue_values[mid:]) / (len(fatigue_values) - mid)
        delta = second_half - first_half
        if delta > 0.05:
            trend = "declining"
        elif delta < -0.05:
            trend = "improving"

    return WeeklyReportResponse(
        scores=[DailyScoreOut.model_validate(s) for s in scores],
        avg_fatigue=avg,
        trend_direction=trend,
    )
