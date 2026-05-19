"""
Kogni Nightly Worker
====================
Runs every midnight via Celery Beat.
For each active user:
  1. Aggregates today's feature vectors → daily mean vector
  2. Scores with RF model → fatigue_score
  3. Pulls last 7 days → scores with LSTM → trajectory_score
  4. Writes both to daily_scores table

Run:
    celery -A nightly_worker worker --beat --loglevel=info
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from celery import Celery
from celery.schedules import crontab

sys.path.insert(0, str(Path(__file__).parent))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kogni.db")
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379/0")

app = Celery("kogni_nightly", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "nightly-score-all-users": {
            "task": "nightly_worker.score_all_users",
            "schedule": crontab(hour=0, minute=0),  # midnight UTC
        },
    },
)


def get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    return Session()


@app.task
def score_all_users():
    """Triggered every midnight — scores every active user."""
    from sqlalchemy import text
    db = get_db()
    try:
        users = db.execute(text("SELECT id FROM users")).fetchall()
        for (uid,) in users:
            score_user.delay(uid)
        return {"queued": len(users)}
    finally:
        db.close()


@app.task
def score_user(user_id: int):
    """
    Full scoring pipeline for one user:
    RF fatigue score + LSTM trajectory score → daily_scores table.
    """
    from sqlalchemy import text
    db = get_db()

    try:
        today = datetime.now(timezone.utc).date()
        since_today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # ── Step 1: Today's mean feature vector ──────────────
        row = db.execute(text("""
            SELECT
                AVG(iki_mean), AVG(iki_std), AVG(hold_mean),
                AVG(error_rate), AVG(key_count), AVG(scroll_velocity),
                AVG(direction_reversals), AVG(scroll_event_count),
                AVG(tab_switches), AVG(hour_of_day), AVG(day_of_week)
            FROM feature_vectors
            WHERE user_id = :uid AND ts >= :since AND key_count > 0
        """), {"uid": user_id, "since": since_today}).fetchone()

        if not row or row[0] is None:
            return {"status": "no_data", "user_id": user_id}

        from features import FEATURE_COLS
        mean_vec = {col: (row[i] or 0) for i, col in enumerate(FEATURE_COLS)}

        # ── Step 2: RF fatigue score ──────────────────────────
        fatigue_score = None
        shap_top3     = []
        try:
            from inference import score_vector
            rf_result     = score_vector(mean_vec)
            fatigue_score = rf_result["fatigue_score"]
            shap_top3     = rf_result["shap_top3"]
        except Exception as e:
            print(f"[RF] Failed for user {user_id}: {e}")

        # ── Step 3: LSTM trajectory score ────────────────────
        trajectory_score = None
        try:
            from lstm_inference import score_user_from_db
            lstm_result      = score_user_from_db(user_id, db)
            if lstm_result:
                trajectory_score = lstm_result["trajectory_score"]
        except Exception as e:
            print(f"[LSTM] Failed for user {user_id}: {e}")

        # ── Step 4: Write to daily_scores ─────────────────────
        shap = shap_top3
        db.execute(text("""
            INSERT INTO daily_scores
                (user_id, date, fatigue_score, trajectory_score,
                 shap_feature_1, shap_value_1,
                 shap_feature_2, shap_value_2,
                 shap_feature_3, shap_value_3)
            VALUES
                (:uid, :date, :fs, :ts,
                 :f1, :v1, :f2, :v2, :f3, :v3)
        """), {
            "uid":  user_id,
            "date": datetime.now(timezone.utc),
            "fs":   fatigue_score,
            "ts":   trajectory_score,
            "f1":   shap[0]["feature"]    if len(shap) > 0 else None,
            "v1":   shap[0]["shap_value"] if len(shap) > 0 else None,
            "f2":   shap[1]["feature"]    if len(shap) > 1 else None,
            "v2":   shap[1]["shap_value"] if len(shap) > 1 else None,
            "f3":   shap[2]["feature"]    if len(shap) > 2 else None,
            "v3":   shap[2]["shap_value"] if len(shap) > 2 else None,
        })
        db.commit()

        return {
            "status":           "ok",
            "user_id":          user_id,
            "fatigue_score":    fatigue_score,
            "trajectory_score": trajectory_score,
        }

    finally:
        db.close()


if __name__ == "__main__":
    # Manual trigger for testing — runs scoring for user 1
    print("Running manual score for user 1...")
    result = score_user(1)
    print(result)
