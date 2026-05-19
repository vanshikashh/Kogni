"""
Kogni Pilot Setup
=================
Seeds the database with realistic behavioral data for
demonstrating the dashboard to pilot users or recruiters.

Creates 8 simulated users with 7 days of behavioral data each,
then runs the full scoring pipeline so the dashboard shows
real charts, SHAP insights, and trajectory scores.

Usage:
    python pilot_setup.py

Run from: kogni-api/ directory (where kogni.db lives)
"""

import sys
import random
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).parent / "kogni.db"
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

# Pilot user profiles — each has a distinct behavioral pattern
PILOT_PROFILES = [
    {"name": "Night Owl",       "peak_hour": 23, "tab_switches": 18, "iki_base": 220, "trend": "declining"},
    {"name": "Morning Focus",   "peak_hour": 9,  "tab_switches": 6,  "iki_base": 175, "trend": "improving"},
    {"name": "Afternoon Slump", "peak_hour": 15, "tab_switches": 12, "iki_base": 195, "trend": "stable"},
    {"name": "Heavy Scroller",  "peak_hour": 21, "tab_switches": 22, "iki_base": 235, "trend": "declining"},
    {"name": "Deep Worker",     "peak_hour": 10, "tab_switches": 4,  "iki_base": 168, "trend": "improving"},
    {"name": "Context Switcher","peak_hour": 14, "tab_switches": 28, "iki_base": 248, "trend": "declining"},
    {"name": "Balanced",        "peak_hour": 11, "tab_switches": 8,  "iki_base": 182, "trend": "stable"},
    {"name": "Recovering",      "peak_hour": 20, "tab_switches": 10, "iki_base": 200, "trend": "improving"},
]


def seed_vectors(db, user_id: int, profile: dict, days: int = 7):
    """Insert realistic feature vectors for a user over N days."""
    rng = np.random.default_rng(user_id * 42)
    now = datetime.now(timezone.utc)

    for day in range(days):
        day_ts = now - timedelta(days=(days - day - 1))
        # Trend modifier
        t = day / (days - 1)
        if profile["trend"] == "declining":
            trend = t
        elif profile["trend"] == "improving":
            trend = 1 - t
        else:
            trend = 0.5

        # Insert 15-20 windows per day (active browsing simulation)
        n_windows = rng.integers(15, 20)
        for w in range(n_windows):
            hour = int(rng.normal(profile["peak_hour"], 2)) % 24
            ts   = day_ts.replace(hour=hour, minute=int(rng.uniform(0, 59)))

            db.execute(text("""
                INSERT INTO feature_vectors
                    (user_id, ts, iki_mean, iki_std, hold_mean, error_rate,
                     key_count, scroll_velocity, direction_reversals,
                     scroll_event_count, tab_switches, hour_of_day,
                     day_of_week, window_duration_s)
                VALUES
                    (:uid, :ts, :iki, :istd, :hold, :err,
                     :kc, :sv, :dr, :sec, :tabs, :hour,
                     :dow, 30)
            """), {
                "uid":  user_id,
                "ts":   ts.isoformat(),
                "iki":  round(profile["iki_base"] + trend*60 + rng.normal(0, 15), 2),
                "istd": round(40 + trend*40 + rng.normal(0, 8), 2),
                "hold": round(80 + trend*25 + rng.normal(0, 10), 2),
                "err":  round(min(0.4, 0.03 + trend*0.1 + rng.uniform(0, 0.02)), 4),
                "kc":   int(max(5, 80 - trend*40 + rng.normal(0, 10))),
                "sv":   round(300 + trend*450 + rng.normal(0, 80), 2),
                "dr":   int(max(0, 2 + trend*8 + rng.normal(0, 2))),
                "sec":  int(max(0, 15 + trend*30 + rng.normal(0, 5))),
                "tabs": int(max(0, profile["tab_switches"] + trend*5 + rng.normal(0, 2))),
                "hour": hour,
                "dow":  day_ts.weekday(),
            })
    db.commit()
    print(f"  ✓ {n_windows * days} vectors inserted")


def score_user(db, user_id: int):
    """Run RF + LSTM scoring for a user."""
    ml_path = Path(__file__).parent.parent / "kogni-ml"
    sys.path.insert(0, str(ml_path))

    # Get mean vector
    row = db.execute(text("""
        SELECT AVG(iki_mean), AVG(iki_std), AVG(hold_mean), AVG(error_rate),
               AVG(key_count), AVG(scroll_velocity), AVG(direction_reversals),
               AVG(scroll_event_count), AVG(tab_switches), AVG(hour_of_day),
               AVG(day_of_week)
        FROM feature_vectors WHERE user_id=:uid AND key_count>0
    """), {"uid": user_id}).fetchone()

    if not row or row[0] is None:
        print("  ✗ No data")
        return

    from features import FEATURE_COLS
    mean_vec = {col: float(row[i] or 0) for i, col in enumerate(FEATURE_COLS)}

    fatigue_score    = None
    trajectory_score = None
    shap_top3        = []

    try:
        from inference import score_vector
        rf_result     = score_vector(mean_vec)
        fatigue_score = rf_result["fatigue_score"]
        shap_top3     = rf_result["shap_top3"]
        print(f"  RF: {fatigue_score} ({rf_result['status']})")
    except Exception as e:
        print(f"  RF failed: {e}")

    try:
        from lstm_inference import score_sequence
        res              = score_sequence([mean_vec])
        trajectory_score = res["trajectory_score"]
        print(f"  LSTM: {trajectory_score} ({res['direction']})")
    except Exception as e:
        print(f"  LSTM failed: {e}")

    shap = shap_top3
    db.execute(text("""
        INSERT INTO daily_scores
            (user_id, date, fatigue_score, trajectory_score,
             shap_feature_1, shap_value_1,
             shap_feature_2, shap_value_2,
             shap_feature_3, shap_value_3)
        VALUES (:uid,:date,:fs,:ts,:f1,:v1,:f2,:v2,:f3,:v3)
    """), {
        "uid":  user_id,
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


def run():
    print("=" * 60)
    print("KOGNI PILOT SETUP")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")

    db = Session()

    # Get existing users
    users = db.execute(text("SELECT id, email FROM users")).fetchall()
    print(f"\nExisting users: {len(users)}")
    for uid, email in users:
        print(f"  User {uid}: {email}")

    if not users:
        print("\n✗ No users found. Register at least one account first.")
        print("  Run the API and register at http://localhost:3000")
        return

    print("\n[SEEDING] Inserting behavioral data...")
    for i, (uid, email) in enumerate(users):
        profile = PILOT_PROFILES[i % len(PILOT_PROFILES)]
        print(f"\n  User {uid} ({email}) — Profile: {profile['name']}")
        seed_vectors(db, uid, profile, days=7)

    print("\n[SCORING] Running RF + LSTM pipeline...")
    for uid, email in users:
        print(f"\n  Scoring user {uid}...")
        score_user(db, uid)

    db.close()

    print("\n" + "=" * 60)
    print("✓ Pilot setup complete!")
    print("  Refresh http://localhost:3000 to see scores")
    print("=" * 60)


if __name__ == "__main__":
    run()
