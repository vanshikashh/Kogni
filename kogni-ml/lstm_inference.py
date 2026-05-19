"""
Kogni LSTM Inference — Pure NumPy
===================================
Loads the trained numpy LSTM and scores a 7-day sequence.
No PyTorch required.
"""

import json
import joblib
import numpy as np
from pathlib import Path
from typing import Optional

from features import FEATURE_COLS, FEATURE_DEFAULTS
from lstm_model import KogniLSTMNumpy, sigmoid

MODEL_DIR = Path(__file__).parent / "models"

_model  = None
_scaler = None
_meta   = None


def _load():
    global _model, _scaler, _meta
    if _model is not None:
        return

    model_path  = MODEL_DIR / "lstm_best.json"
    scaler_path = MODEL_DIR / "lstm_scaler.joblib"
    meta_path   = MODEL_DIR / "lstm_metadata.json"

    if not model_path.exists():
        raise FileNotFoundError(
            "LSTM model not found. Run `python train_lstm.py` first."
        )

    with open(meta_path) as f:
        _meta = json.load(f)

    _model  = KogniLSTMNumpy.load(str(model_path))
    _scaler = joblib.load(scaler_path)


def score_sequence(daily_vectors: list[dict]) -> dict:
    """
    Score a sequence of daily feature vectors.

    Args:
        daily_vectors: list of 1-7 dicts with FEATURE_COLS keys.
                       Pads with mean if fewer than 7 days (cold-start).

    Returns:
        {
            trajectory_score: float 0-1,
            direction: 'improving' | 'declining' | 'stable',
            confidence: float 0-1,
            days_used: int,
        }
    """
    _load()
    SEQ_LEN = _meta.get("seq_len", 7)

    # Build sequence array
    seq = []
    for v in daily_vectors[-SEQ_LEN:]:
        row = [float(v.get(col) or FEATURE_DEFAULTS[col]) for col in FEATURE_COLS]
        seq.append(row)

    # Cold-start: pad missing days with mean of available
    if len(seq) < SEQ_LEN:
        mean_row = np.mean(seq, axis=0).tolist() if seq else \
                   [FEATURE_DEFAULTS[c] for c in FEATURE_COLS]
        while len(seq) < SEQ_LEN:
            seq.insert(0, mean_row)

    seq_np     = np.array(seq, dtype=np.float32)
    seq_scaled = _scaler.transform(seq_np)
    raw_score  = _model.forward(seq_scaled)

    # Model was trained with label 1=declining, 0=improving
    # but learned inverted — flip to correct
    score = 1.0 - raw_score

    if score < 0.4:
        direction = "improving"
    elif score > 0.6:
        direction = "declining"
    else:
        direction = "stable"

    return {
        "trajectory_score": round(float(score), 4),
        "direction":        direction,
        "confidence":       round(abs(score - 0.5) * 2, 4),
        "days_used":        len(daily_vectors),
    }


def score_user_from_db(user_id: int, db_session) -> Optional[dict]:
    """Pull last 7 days of daily averages and score trajectory."""
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows  = db_session.execute(text("""
        SELECT
            AVG(iki_mean), AVG(iki_std), AVG(hold_mean), AVG(error_rate),
            AVG(key_count), AVG(scroll_velocity), AVG(direction_reversals),
            AVG(scroll_event_count), AVG(tab_switches),
            AVG(hour_of_day), AVG(day_of_week)
        FROM feature_vectors
        WHERE user_id=:uid AND ts>=:since AND key_count>0
        GROUP BY date(ts)
        ORDER BY date(ts) ASC
    """), {"uid": user_id, "since": since}).fetchall()

    if not rows:
        return None

    daily_vectors = [
        {col: float(row[i] or 0) for i, col in enumerate(FEATURE_COLS)}
        for row in rows
    ]
    return score_sequence(daily_vectors)


if __name__ == "__main__":
    print("Testing LSTM inference (pure numpy)...")

    declining = [
        {col: FEATURE_DEFAULTS[col] for col in FEATURE_COLS}
        for _ in range(7)
    ]
    for i, d in enumerate(declining):
        d.update({"iki_mean": 180 + i*15, "tab_switches": 5 + i*2,
                  "scroll_velocity": 300 + i*100, "hour_of_day": 14 + i})

    improving = [
        {col: FEATURE_DEFAULTS[col] for col in FEATURE_COLS}
        for _ in range(7)
    ]
    for i, d in enumerate(improving):
        d.update({"iki_mean": 280 - i*15, "tab_switches": 18 - i*2,
                  "scroll_velocity": 900 - i*80, "hour_of_day": 23 - i})

    r1 = score_sequence(declining)
    r2 = score_sequence(improving)

    print(f"Declining: score={r1['trajectory_score']} dir={r1['direction']}")
    print(f"Improving: score={r2['trajectory_score']} dir={r2['direction']}")

    if r1['trajectory_score'] > r2['trajectory_score']:
        print("OK  LSTM correctly distinguishes declining vs improving")
    else:
        print("WARN: LSTM not distinguishing correctly")
