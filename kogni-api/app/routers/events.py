from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.event import FeatureVector, DailyScore
from app.schemas.schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest(
    body: IngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Receive a batch of feature vectors from the Chrome extension.
    Vectors are stored immediately. ML inference is async (Celery — Phase 2).
    Returns the latest fatigue score if one exists for this user.
    """
    rows = []
    for v in body.vectors:
        row = FeatureVector(
            user_id=current_user.id,
            iki_mean=v.iki_mean,
            iki_std=v.iki_std,
            hold_mean=v.hold_mean,
            error_rate=v.error_rate,
            key_count=v.key_count or 0,
            scroll_velocity=v.scroll_velocity,
            direction_reversals=v.direction_reversals or 0,
            scroll_event_count=v.scroll_event_count or 0,
            tab_switches=v.tab_switches or 0,
            hour_of_day=v.hour_of_day,
            day_of_week=v.day_of_week,
            window_duration_s=v.window_duration_s or 30,
        )
        rows.append(row)

    db.bulk_save_objects(rows)
    db.commit()

    # Fire async ML job for the most recent vector (latest has most signal)
    if rows:
        latest_vec = {
            "iki_mean":            body.vectors[-1].iki_mean,
            "iki_std":             body.vectors[-1].iki_std,
            "hold_mean":           body.vectors[-1].hold_mean,
            "error_rate":          body.vectors[-1].error_rate,
            "key_count":           body.vectors[-1].key_count,
            "scroll_velocity":     body.vectors[-1].scroll_velocity,
            "direction_reversals": body.vectors[-1].direction_reversals,
            "scroll_event_count":  body.vectors[-1].scroll_event_count,
            "tab_switches":        body.vectors[-1].tab_switches,
            "hour_of_day":         body.vectors[-1].hour_of_day,
            "day_of_week":         body.vectors[-1].day_of_week,
        }
        try:
            from kogni_ml.worker import score_realtime
            score_realtime.delay(current_user.id, latest_vec)
        except Exception:
            pass  # worker not running — graceful degradation

    # Return latest cached fatigue score (set by worker via Redis)
    import redis, json as _json, os
    fatigue_score = None
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        cached = r.get(f"kogni:score:{current_user.id}")
        if cached:
            fatigue_score = _json.loads(cached).get("fatigue_score")
    except Exception:
        pass

    return IngestResponse(
        accepted=len(rows),
        fatigue_score=fatigue_score,
    )
