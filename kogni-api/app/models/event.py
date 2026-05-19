from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class FeatureVector(Base):
    """
    One row per 30-second active window per user.
    This is the raw behavioral signal table.
    TimescaleDB will partition this by ts in production.
    """
    __tablename__ = "feature_vectors"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ts              = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Keystroke features
    iki_mean        = Column(Float, nullable=True)   # inter-key interval mean (ms)
    iki_std         = Column(Float, nullable=True)   # inter-key interval std dev (ms)
    hold_mean       = Column(Float, nullable=True)   # key hold duration mean (ms)
    error_rate      = Column(Float, nullable=True)   # backspace / total keys
    key_count       = Column(Integer, default=0)

    # Scroll features
    scroll_velocity       = Column(Float, nullable=True)   # px/sec
    direction_reversals   = Column(Integer, default=0)
    scroll_event_count    = Column(Integer, default=0)

    # Session context
    tab_switches          = Column(Integer, default=0)
    hour_of_day           = Column(Integer, nullable=True)   # 0–23
    day_of_week           = Column(Integer, nullable=True)   # 0=Mon … 6=Sun
    window_duration_s     = Column(Integer, default=30)

    user = relationship("User", back_populates="feature_vectors")


class DailyScore(Base):
    """
    One row per user per day — computed nightly by Celery.
    """
    __tablename__ = "daily_scores"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date            = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    fatigue_score   = Column(Float, nullable=True)    # 0–1, from Random Forest
    trajectory_score = Column(Float, nullable=True)   # 0–1, from LSTM (weekly)

    # Top SHAP drivers (stored as strings for dashboard display)
    shap_feature_1  = Column(String, nullable=True)
    shap_value_1    = Column(Float, nullable=True)
    shap_feature_2  = Column(String, nullable=True)
    shap_value_2    = Column(Float, nullable=True)
    shap_feature_3  = Column(String, nullable=True)
    shap_value_3    = Column(Float, nullable=True)

    user = relationship("User", back_populates="daily_scores")
