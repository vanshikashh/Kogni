"""
Kogni Scorer - Safe Version
Updates today's score, never creates duplicates.
Put this in kogni-ml/ as score_now.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Find the database
DB_PATH = Path(__file__).parent.parent / "kogni-api" / "kogni.db"
if not DB_PATH.exists():
    DB_PATH = Path(__file__).parent.parent / "kogni.db"
if not DB_PATH.exists():
    print(f"ERROR: Cannot find kogni.db. Looked in:")
    print(f"  {Path(__file__).parent.parent / 'kogni-api' / 'kogni.db'}")
    sys.exit(1)

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

        for uid, email in users:
            print(f"Scoring user {uid} ({email})...")
            today = datetime.now(timezone.utc).date()

            count = db.execute(text(
                "SELECT COUNT(*) FROM feature_vectors WHERE user_id=:uid AND key_count>0"
            ), {"uid": uid}).fetchone()[0]

            if count == 0:
                print(f"  No data yet — browse with the extension first\n")
                continue

            print(f"  Vectors: {count}")

            row = db.execute(text("""
                SELECT AVG(iki_mean), AVG(iki_std), AVG(hold_mean), AVG(error_rate),
                       AVG(key_count), AVG(scroll_velocity), AVG(direction_reversals),
                       AVG(scroll_event_count), AVG(tab_switches),
                       AVG(hour_of_day), AVG(day_of_week)
                FROM feature_vectors WHERE user_id=:uid AND key_count>0
            """), {"uid": uid}).fetchone()

            mean_vec = {col: float(row[i] or 0) for i, col in enumerate(FEATURE_COLS)}

            fatigue_score = None
            shap_top3 = []
            try:
                from inference import score_vector
                rf = score_vector(mean_vec)
                fatigue_score = rf["fatigue_score"]
                shap_top3 = rf["shap_top3"]
                print(f"  RF: {fatigue_score} ({rf['status']})")
            except Exception as e:
                print(f"  RF failed: {e}")

            trajectory_score = None
            try:
                from lstm_inference import score_sequence
                since = datetime.now(timezone.utc) - timedelta(days=14)
                rows = db.execute(text("""
                    SELECT AVG(iki_mean),AVG(iki_std),AVG(hold_mean),AVG(error_rate),
                           AVG(key_count),AVG(scroll_velocity),AVG(direction_reversals),
                           AVG(scroll_event_count),AVG(tab_switches),
                           AVG(hour_of_day),AVG(day_of_week)
                    FROM feature_vectors
                    WHERE user_id=:uid AND ts>=:since AND key_count>0
                    GROUP BY date(ts) ORDER BY date(ts)
                """), {"uid": uid, "since": since}).fetchall()
                if rows:
                    daily = [{col: float(r[i] or 0) for i,col in enumerate(FEATURE_COLS)} for r in rows]
                    lstm = score_sequence(daily)
                    trajectory_score = lstm["trajectory_score"]
                    print(f"  LSTM: {trajectory_score} ({lstm['direction']})")
            except Exception as e:
                print(f"  LSTM failed: {e}")

            shap = shap_top3
            params = {
                "uid": uid,
                "date": datetime.now(timezone.utc).isoformat(),
                "today": str(today),
                "fs": fatigue_score, "ts": trajectory_score,
                "f1": shap[0]["feature"]    if len(shap)>0 else None,
                "v1": shap[0]["shap_value"] if len(shap)>0 else None,
                "f2": shap[1]["feature"]    if len(shap)>1 else None,
                "v2": shap[1]["shap_value"] if len(shap)>1 else None,
                "f3": shap[2]["feature"]    if len(shap)>2 else None,
                "v3": shap[2]["shap_value"] if len(shap)>2 else None,
            }

            existing = db.execute(text(
                "SELECT id FROM daily_scores WHERE user_id=:uid AND date(date)=:today"
            ), {"uid": uid, "today": str(today)}).fetchone()

            if existing:
                db.execute(text("""
                    UPDATE daily_scores SET
                        fatigue_score=:fs, trajectory_score=:ts, date=:date,
                        shap_feature_1=:f1, shap_value_1=:v1,
                        shap_feature_2=:f2, shap_value_2=:v2,
                        shap_feature_3=:f3, shap_value_3=:v3
                    WHERE user_id=:uid AND date(date)=:today
                """), params)
                print(f"  ✓ Updated today's score")
            else:
                db.execute(text("""
                    INSERT INTO daily_scores
                        (user_id, date, fatigue_score, trajectory_score,
                         shap_feature_1, shap_value_1,
                         shap_feature_2, shap_value_2,
                         shap_feature_3, shap_value_3)
                    VALUES (:uid,:date,:fs,:ts,:f1,:v1,:f2,:v2,:f3,:v3)
                """), params)
                print(f"  ✓ Created today's score")

            db.commit()
            print()

        print("Done. Refresh http://localhost:3000")
    finally:
        db.close()

if __name__ == "__main__":
    score_all()
