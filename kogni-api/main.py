"""
Kogni API — Single File, SQLite, No External Dependencies
==========================================================
Auth, ingestion, dashboard, recovery — everything in one file.
Uses SQLite so zero Docker/PostgreSQL setup required.
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (create_engine, Column, Integer, String, Float,
                        DateTime, Boolean, ForeignKey, event as sa_event, text)
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import Optional
import sqlite3, os, numpy as np

# ── Config ────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kogni.db")
SECRET_KEY   = os.getenv("SECRET_KEY",   "kogni-local-secret-change-in-prod")
ALGORITHM    = "HS256"
TOKEN_DAYS   = 7

# ── Database ──────────────────────────────────────────────
engine      = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
pwd_context  = CryptContext(schemes=["bcrypt"], deprecated="auto")

@sa_event.listens_for(Engine, "connect")
def sqlite_fk(dbapi_conn, _):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    email      = Column(String, unique=True, index=True)
    password   = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FeatureVector(Base):
    __tablename__ = "feature_vectors"
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey("users.id"), index=True)
    ts                  = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    iki_mean            = Column(Float,   nullable=True)
    iki_std             = Column(Float,   nullable=True)
    hold_mean           = Column(Float,   nullable=True)
    error_rate          = Column(Float,   nullable=True)
    key_count           = Column(Integer, default=0)
    scroll_velocity     = Column(Float,   nullable=True)
    direction_reversals = Column(Integer, default=0)
    scroll_event_count  = Column(Integer, default=0)
    tab_switches        = Column(Integer, default=0)
    hour_of_day         = Column(Integer, nullable=True)
    day_of_week         = Column(Integer, nullable=True)
    window_duration_s   = Column(Integer, default=30)

class DailyScore(Base):
    __tablename__ = "daily_scores"
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey("users.id"), index=True)
    date             = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    fatigue_score    = Column(Float,  nullable=True)
    trajectory_score = Column(Float,  nullable=True)
    shap_feature_1   = Column(String, nullable=True)
    shap_value_1     = Column(Float,  nullable=True)
    shap_feature_2   = Column(String, nullable=True)
    shap_value_2     = Column(Float,  nullable=True)
    shap_feature_3   = Column(String, nullable=True)
    shap_value_3     = Column(Float,  nullable=True)

class Intervention(Base):
    __tablename__ = "interventions"
    id            = Column(Integer,  primary_key=True)
    user_id       = Column(Integer,  ForeignKey("users.id"), index=True)
    triggered_at  = Column(DateTime(timezone=True), server_default=func.now())
    pre_score     = Column(Float,   nullable=True)
    post_iki_mean = Column(Float,   nullable=True)
    post_iki_std  = Column(Float,   nullable=True)
    keystrokes    = Column(Integer, default=0)
    recovered     = Column(Boolean, default=False)
    passage_id    = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="Kogni API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:    yield db
    finally: db.close()

def make_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id),
         "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)},
        SECRET_KEY, algorithm=ALGORITHM
    )

def current_user(authorization: Optional[str] = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.replace("Bearer ", "").replace("bearer ", "").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user

# ── Schemas ───────────────────────────────────────────────
class AuthBody(BaseModel):
    email: str
    password: str

class FeatureVectorIn(BaseModel):
    ts:                  Optional[int]   = None
    window_duration_s:   Optional[int]   = 30
    iki_mean:            Optional[float] = None
    iki_std:             Optional[float] = None
    hold_mean:           Optional[float] = None
    error_rate:          Optional[float] = None
    key_count:           Optional[int]   = 0
    scroll_velocity:     Optional[float] = None
    direction_reversals: Optional[int]   = 0
    scroll_event_count:  Optional[int]   = 0
    tab_switches:        Optional[int]   = 0
    hour_of_day:         Optional[int]   = None
    day_of_week:         Optional[int]   = None

class IngestBody(BaseModel):
    vectors: list[FeatureVectorIn]

class MeasureBody(BaseModel):
    keystroke_timings: list[int]
    pre_score:         Optional[float] = None
    passage_id:        Optional[int]   = 0

# ── Auth ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "kogni-api", "version": "0.1.0"}

@app.post("/api/v1/auth/register", status_code=201)
def register(body: AuthBody, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(email=body.email, password=pwd_context.hash(body.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": make_token(user.id), "token_type": "bearer"}

@app.post("/api/v1/auth/login")
def login(body: AuthBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not pwd_context.verify(body.password, user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": make_token(user.id), "token_type": "bearer"}

# ── Ingestion ─────────────────────────────────────────────
@app.post("/api/v1/events/ingest", status_code=202)
def ingest(body: IngestBody,
           db: Session = Depends(get_db),
           user: User = Depends(current_user)):
    rows = [
        FeatureVector(
            user_id=user.id,
            iki_mean=v.iki_mean, iki_std=v.iki_std, hold_mean=v.hold_mean,
            error_rate=v.error_rate, key_count=v.key_count or 0,
            scroll_velocity=v.scroll_velocity,
            direction_reversals=v.direction_reversals or 0,
            scroll_event_count=v.scroll_event_count or 0,
            tab_switches=v.tab_switches or 0,
            hour_of_day=v.hour_of_day, day_of_week=v.day_of_week,
            window_duration_s=v.window_duration_s or 30,
        ) for v in body.vectors
    ]
    db.bulk_save_objects(rows); db.commit()
    total = db.query(FeatureVector).filter(FeatureVector.user_id == user.id).count()
    return {"accepted": len(rows), "total_vectors": total, "fatigue_score": None}

# ── Dashboard ─────────────────────────────────────────────
@app.get("/api/v1/dashboard/weekly-report")
def weekly_report(db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    since  = datetime.now(timezone.utc) - timedelta(days=7)
    scores = (db.query(DailyScore)
                .filter(DailyScore.user_id == user.id, DailyScore.date >= since)
                .order_by(DailyScore.date.asc()).all())

    fv     = [s.fatigue_score    for s in scores if s.fatigue_score    is not None]
    tv     = [s.trajectory_score for s in scores if s.trajectory_score is not None]
    avg_f  = round(sum(fv)/len(fv), 4) if fv else None
    avg_t  = round(sum(tv)/len(tv), 4) if tv else None

    trend = "stable"
    if tv:
        trend = "improving" if tv[-1] < 0.4 else "declining" if tv[-1] > 0.6 else "stable"
    elif len(fv) >= 4:
        mid = len(fv)//2
        d   = sum(fv[mid:])/len(fv[mid:]) - sum(fv[:mid])/mid
        trend = "declining" if d > 0.05 else "improving" if d < -0.05 else "stable"

    total = db.query(FeatureVector).filter(FeatureVector.user_id == user.id).count()
    return {
        "scores": [{
            "date":             s.date.isoformat(),
            "fatigue_score":    s.fatigue_score,
            "trajectory_score": s.trajectory_score,
            "shap_feature_1":   s.shap_feature_1, "shap_value_1": s.shap_value_1,
            "shap_feature_2":   s.shap_feature_2, "shap_value_2": s.shap_value_2,
            "shap_feature_3":   s.shap_feature_3, "shap_value_3": s.shap_value_3,
        } for s in scores],
        "avg_fatigue":     avg_f,
        "avg_trajectory":  avg_t,
        "trend_direction": trend,
        "total_vectors":   total,
    }

# ── Recovery ──────────────────────────────────────────────
PASSAGES = [
    "The system quietly observes how you type and scroll. It builds a picture of your cognitive rhythm over time. When that rhythm shifts, it notices. This exercise helps it measure where you are right now.",
    "Focus is not a switch you flip. It builds slowly and depletes faster than most people realize. Taking a short pause to type at your natural pace gives your attention a moment to reset.",
    "Every keystroke carries timing information. The gaps between keys, the hesitations, the small corrections — all of these form a pattern unique to you. That pattern changes when your mind is tired.",
    "Cognitive health is not visible the way physical health sometimes is. But it leaves traces in behavior. The way you type when you are sharp is different from the way you type when you are not.",
    "A few minutes of deliberate, unhurried typing can help restore the rhythm that sustained focus requires. There is no rush here. Type at whatever pace feels natural to you right now.",
]

@app.get("/api/v1/recovery/passage")
def get_passage(db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    idx = (user.id + datetime.now().day) % len(PASSAGES)
    return {"passage_id": idx, "text": PASSAGES[idx]}

@app.post("/api/v1/recovery/measure")
def measure_recovery(body: MeasureBody,
                     db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    since = datetime.now(timezone.utc) - timedelta(days=7)
    row   = db.execute(text("""
        SELECT AVG(iki_mean) FROM feature_vectors
        WHERE user_id=:uid AND ts>=:since AND iki_mean IS NOT NULL AND key_count>5
    """), {"uid": user.id, "since": since}).fetchone()
    baseline = float(row[0]) if row and row[0] else None

    t    = sorted(body.keystroke_timings)
    ikis = [t[i]-t[i-1] for i in range(1, len(t)) if 50 < t[i]-t[i-1] < 3000]
    if not ikis:
        return {"recovered": False, "message": "Not enough typing data — type more."}

    post_iki  = float(np.mean(ikis))
    post_std  = float(np.std(ikis))
    pct       = abs(post_iki - baseline) / baseline if baseline else None
    recovered = (pct <= 0.15) if pct is not None else True
    message   = (f"Rhythm restored — within {pct*100:.1f}% of baseline." if recovered
                 else f"Still elevated — {pct*100:.1f}% above baseline.") if pct else "Baseline not yet established."

    db.execute(text("""
        INSERT INTO interventions
            (user_id, triggered_at, pre_score, post_iki_mean,
             post_iki_std, keystrokes, recovered, passage_id)
        VALUES (:uid,:ts,:pre,:piki,:pstd,:ks,:rec,:pid)
    """), {
        "uid": user.id, "ts": datetime.now(timezone.utc).isoformat(),
        "pre": body.pre_score, "piki": round(post_iki, 2),
        "pstd": round(post_std, 2), "ks": len(body.keystroke_timings),
        "rec": 1 if recovered else 0, "pid": body.passage_id or 0,
    })
    db.commit()
    return {
        "recovered":       recovered,
        "post_iki_mean":   round(post_iki, 2),
        "post_iki_std":    round(post_std, 2),
        "baseline_iki":    round(baseline, 2) if baseline else None,
        "pct_of_baseline": round(pct, 4) if pct else None,
        "message":         message,
    }

@app.get("/api/v1/recovery/history")
def recovery_history(db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    rows = db.execute(text("""
        SELECT triggered_at, pre_score, post_iki_mean, keystrokes, recovered, passage_id
        FROM interventions WHERE user_id=:uid ORDER BY triggered_at DESC LIMIT 10
    """), {"uid": user.id}).fetchall()
    return {"history": [
        {"triggered_at": r[0], "pre_score": r[1], "post_iki_mean": r[2],
         "keystrokes": r[3], "recovered": bool(r[4]), "passage_id": r[5]}
        for r in rows
    ]}
