"""
Kogni Manual Scorer
===================
Run this manually to score all users without Celery.
No Redis, no Docker needed.

Usage:
    cd kogni-ml
    python score_now.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# DB is in kogni-api/
DB_PATH = Path(__file__).parent.parent / "kogni-api" / "kogni.db"
if not DB_PATH.exists():
    # Try current dir fallback
    DB_PATH = Path(__file__).parent.parent / "kogni.db"

print(f"Database: {DB_PATH}")
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

FEATURE_COLS = [
    "iki_mean","iki_std","hold_mean","error_rate","key_count",
    "scroll_velocity","direction_reversals","scroll_event_count",
    "tab_switches","hour_of_day","day_of_week"
]


def score_all():
    db = Session()
    try:
        users = db.execute(text("SELECT id, email FROM users")).fetchall()
        print(f"Found {len(users)} user(s)\n")

        if not users:
            print("No users found. Register first at http://localhost:3000")
            return

        for uid, email in users:
            print(f"Scoring user {uid} ({email})...")

            # Check vector count
            count = db.execute(text(
                "SELECT COUNT(*) FROM feature_vectors WHERE user_id=:uid AND key_count>0"
            ), {"uid": uid}).fetchone()[0]

            if count == 0:
                print(f"  No behavioral data yet — browse with the extension first\n")
                continue

            print(f"  Vectors available: {count}")

            # Mean feature vector across all data
            row = db.execute(text("""
                SELECT AVG(iki_mean), AVG(iki_std), AVG(hold_mean), AVG(error_rate),
                       AVG(key_count), AVG(scroll_velocity), AVG(direction_reversals),
                       AVG(scroll_event_count), AVG(tab_switches),
                       AVG(hour_of_day), AVG(day_of_week)
                FROM feature_vectors WHERE user_id=:uid AND key_count>0
            """), {"uid": uid}).fetchone()

            mean_vec = {col: float(row[i] or 0) for i, col in enumerate(FEATURE_COLS)}

            # RF score
            fatigue_score = None
            shap_top3     = []
            try:
                from inference import score_vector
                rf            = score_vector(mean_vec)
                fatigue_score = rf["fatigue_score"]
                shap_top3     = rf["shap_top3"]
                print(f"  RF  fatigue_score : {fatigue_score} ({rf['status']})")
            except Exception as e:
                print(f"  RF  failed: {e}")

            # LSTM score
            trajectory_score = None
            try:
                from lstm_inference import score_sequence
                since = datetime.now(timezone.utc) - timedelta(days=7)
                rows  = db.execute(text("""
                    SELECT AVG(iki_mean),AVG(iki_std),AVG(hold_mean),AVG(error_rate),
                           AVG(key_count),AVG(scroll_velocity),AVG(direction_reversals),
                           AVG(scroll_event_count),AVG(tab_switches),
                           AVG(hour_of_day),AVG(day_of_week)
                    FROM feature_vectors
                    WHERE user_id=:uid AND ts>=:since AND key_count>0
                    GROUP BY date(ts) ORDER BY date(ts)
                """), {"uid": uid, "since": since}).fetchall()

                if rows:
                    daily = [{col: float(r[i] or 0) for i, col in enumerate(FEATURE_COLS)}
                             for r in rows]
                    lstm  = score_sequence(daily)
                    trajectory_score = lstm["trajectory_score"]
                    print(f"  LSTM trajectory  : {trajectory_score} ({lstm['direction']})")
            except Exception as e:
                print(f"  LSTM failed: {e}")

            # Write to daily_scores
            shap = shap_top3
            db.execute(text("""
                INSERT INTO daily_scores
                    (user_id, date, fatigue_score, trajectory_score,
                     shap_feature_1, shap_value_1,
                     shap_feature_2, shap_value_2,
                     shap_feature_3, shap_value_3)
                VALUES (:uid,:date,:fs,:ts,:f1,:v1,:f2,:v2,:f3,:v3)
            """), {
                "uid":  uid,
                "date": datetime.now(timezone.utc).isoformat(),
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
            print(f"  ✓ Written to daily_scores\n")

        print("Done. Refresh http://localhost:3000 to see updated scores.")
    finally:
        db.close()


if __name__ == "__main__":
    score_all()
