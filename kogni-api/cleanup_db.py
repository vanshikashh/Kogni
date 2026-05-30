"""
Run this once to clean up duplicate daily_scores.
Keeps only the latest score per user per day.
Put in kogni-api/ and run: python cleanup_db.py
"""
from sqlalchemy import create_engine, text
from pathlib import Path

DB_PATH = Path(__file__).parent / "kogni.db"
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

with engine.connect() as db:
    # Find all users
    users = db.execute(text("SELECT id, email FROM users")).fetchall()
    
    for uid, email in users:
        # Get all scores for this user
        scores = db.execute(text("""
            SELECT id, date(date) as day, date, fatigue_score
            FROM daily_scores 
            WHERE user_id=:uid
            ORDER BY date DESC
        """), {"uid": uid}).fetchall()
        
        # Group by day, keep only the latest id per day
        seen_days = {}
        to_delete = []
        for row in scores:
            sid, day, dt, fs = row
            if day not in seen_days:
                seen_days[day] = sid  # keep this one
            else:
                to_delete.append(sid)  # delete this duplicate
        
        if to_delete:
            for sid in to_delete:
                db.execute(text("DELETE FROM daily_scores WHERE id=:sid"), {"sid": sid})
            print(f"User {uid} ({email}): removed {len(to_delete)} duplicates, kept {len(seen_days)} days")
        else:
            print(f"User {uid} ({email}): no duplicates found")
    
    db.commit()
    print("\nDone. Database cleaned up.")
