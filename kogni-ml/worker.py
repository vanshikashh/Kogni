"""
Kogni Celery Worker
===================
Async ML inference jobs triggered after feature vector ingestion.

Jobs:
    score_realtime   — RF inference on latest window, push score via Redis pub/sub
    nightly_summary  — aggregate day's vectors → daily_scores table
    check_recovery   — detect if fatigue threshold exceeded → trigger intervention

Start worker:
    celery -A worker worker --loglevel=info
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from celery import Celery
import redis

# Add parent dir so we can import inference
sys.path.insert(0, str(Path(__file__).parent))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kogni:kogni@localhost:5432/kogni")

app = Celery("kogni", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Beat schedule for nightly tasks
    beat_schedule={
        "nightly-summary": {
            "task": "worker.nightly_summary_all_users",
            "schedule": 86400,  # every 24 hours
        },
    },
)

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Lazy-load inference to avoid loading model at import time
_inference = None
def get_inference():
    global _inference
    if _inference is None:
        from inference import score_vector, score_batch
        _inference = {"single": score_vector, "batch": score_batch}
    return _inference


# ── Task 1: Real-time RF scoring ──────────────────────────

@app.task(bind=True, max_retries=2)
def score_realtime(self, user_id: int, vector: dict):
    """
    Score a single feature vector immediately after ingestion.
    Publishes result to Redis channel for WebSocket delivery.
    """
    try:
        inf = get_inference()
        result = inf["single"](vector)

        payload = {
            "user_id":      user_id,
            "fatigue_score": result["fatigue_score"],
            "status":        result["status"],
            "shap_top3":    result["shap_top3"],
            "ts":           datetime.now(timezone.utc).isoformat(),
        }

        # Publish to Redis — FastAPI WebSocket handler subscribes
        redis_client.publish(
            f"kogni:live:{user_id}",
            json.dumps(payload)
        )

        # Cache latest score (60 min TTL)
        redis_client.setex(
            f"kogni:score:{user_id}",
            3600,
            json.dumps(payload)
        )

        # Check fatigue threshold — trigger recovery if needed
        check_recovery_threshold.delay(user_id, result["fatigue_score"])

        return payload

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)


# ── Task 2: Recovery threshold check ─────────────────────

@app.task
def check_recovery_threshold(user_id: int, fatigue_score: float, threshold: float = 0.75):
    """
    Track consecutive high-fatigue readings.
    If 3 in a row exceed threshold → push recovery intervention.
    """
    key = f"kogni:highfatigue:{user_id}"
    count_raw = redis_client.get(key)
    count = int(count_raw) if count_raw else 0

    if fatigue_score >= threshold:
        count += 1
        redis_client.setex(key, 1800, count)  # 30min TTL resets streak
    else:
        redis_client.delete(key)
        count = 0

    if count >= 3:
        # Push intervention signal
        intervention = {
            "type":         "recovery_intervention",
            "user_id":      user_id,
            "fatigue_score": fatigue_score,
            "consecutive":  count,
            "task_type":    "typing_rhythm",
            "message":      "Your focus rhythm has been elevated for a while. A quick typing exercise may help.",
        }
        redis_client.publish(f"kogni:live:{user_id}", json.dumps(intervention))
        redis_client.delete(key)  # reset streak after triggering


# ── Task 3: Nightly daily score summary ───────────────────

@app.task
def nightly_summary(user_id: int):
    """
    Aggregate today's feature vectors from DB → compute daily score.
    Write to daily_scores table with top SHAP drivers.

    Called by Celery Beat at midnight UTC.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        # Fetch today's feature vectors
        today = datetime.now(timezone.utc).date()
        rows = db.execute(text("""
            SELECT iki_mean, iki_std, hold_mean, error_rate, key_count,
                   scroll_velocity, direction_reversals, scroll_event_count,
                   tab_switches, hour_of_day, day_of_week
            FROM feature_vectors
            WHERE user_id = :uid
              AND ts >= :start
              AND ts < :end
              AND key_count > 0
        """), {"uid": user_id, "start": today, "end": today + timedelta(days=1)}).fetchall()

        if not rows:
            return {"status": "no_data", "user_id": user_id}

        # Compute mean feature vector across the day
        import numpy as np
        cols = ["iki_mean","iki_std","hold_mean","error_rate","key_count",
                "scroll_velocity","direction_reversals","scroll_event_count",
                "tab_switches","hour_of_day","day_of_week"]

        arr = np.array([[r[i] if r[i] is not None else 0 for i in range(len(cols))] for r in rows])
        mean_vec = {col: float(arr[:, i].mean()) for i, col in enumerate(cols)}

        # Score the daily mean vector
        inf = get_inference()
        result = inf["single"](mean_vec)

        # Write to daily_scores
        shap = result["shap_top3"]
        db.execute(text("""
            INSERT INTO daily_scores
                (user_id, date, fatigue_score, shap_feature_1, shap_value_1,
                 shap_feature_2, shap_value_2, shap_feature_3, shap_value_3)
            VALUES
                (:uid, :date, :score,
                 :f1, :v1, :f2, :v2, :f3, :v3)
            ON CONFLICT (user_id, date::date) DO UPDATE
                SET fatigue_score=EXCLUDED.fatigue_score,
                    shap_feature_1=EXCLUDED.shap_feature_1,
                    shap_value_1=EXCLUDED.shap_value_1,
                    shap_feature_2=EXCLUDED.shap_feature_2,
                    shap_value_2=EXCLUDED.shap_value_2,
                    shap_feature_3=EXCLUDED.shap_feature_3,
                    shap_value_3=EXCLUDED.shap_value_3
        """), {
            "uid":   user_id,
            "date":  today,
            "score": result["fatigue_score"],
            "f1": shap[0]["feature"] if len(shap) > 0 else None,
            "v1": shap[0]["shap_value"] if len(shap) > 0 else None,
            "f2": shap[1]["feature"] if len(shap) > 1 else None,
            "v2": shap[1]["shap_value"] if len(shap) > 1 else None,
            "f3": shap[2]["feature"] if len(shap) > 2 else None,
            "v3": shap[2]["shap_value"] if len(shap) > 2 else None,
        })
        db.commit()

    return {"status": "ok", "user_id": user_id, "score": result["fatigue_score"]}


@app.task
def nightly_summary_all_users():
    """Beat task: run nightly_summary for every active user."""
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        users = conn.execute(text("SELECT id FROM users WHERE is_active=true")).fetchall()
    for (uid,) in users:
        nightly_summary.delay(uid)
    return {"queued": len(users)}
