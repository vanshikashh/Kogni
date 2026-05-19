"""
Kogni Inference Engine
======================
Loads the trained RF pipeline and SHAP explainer.
Used by the Celery worker to score incoming feature vectors.

Returns:
    fatigue_score: float 0–1
    shap_top3: list of {feature, label, value, direction}
"""

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from features import FEATURE_COLS, FEATURE_LABELS, FEATURE_DEFAULTS

MODEL_DIR = Path(__file__).parent / "models"

_pipeline  = None
_explainer = None
_metadata  = None


def _load():
    global _pipeline, _explainer, _metadata
    if _pipeline is not None:
        return

    pipeline_path  = MODEL_DIR / "rf_pipeline.joblib"
    explainer_path = MODEL_DIR / "shap_explainer.joblib"
    meta_path      = MODEL_DIR / "metadata.json"

    if not pipeline_path.exists():
        raise FileNotFoundError(
            f"Model not found at {pipeline_path}. "
            "Run `python train.py` first."
        )

    _pipeline  = joblib.load(pipeline_path)
    _explainer = joblib.load(explainer_path)
    with open(meta_path) as f:
        _metadata = json.load(f)


def score_vector(vector: dict) -> dict:
    """
    Score a single feature vector.

    Args:
        vector: dict with keys matching FEATURE_COLS (missing keys filled with defaults)

    Returns:
        {
            fatigue_score: float,       # 0–1 probability of high fatigue
            fatigue_class: int,         # 0 or 1
            status: str,                # "nominal" | "moderate" | "high"
            shap_top3: list[dict],      # top 3 behavioral drivers
        }
    """
    _load()

    # Build feature row with defaults for any missing values
    row = {col: vector.get(col, FEATURE_DEFAULTS[col]) for col in FEATURE_COLS}
    X   = pd.DataFrame([row])[FEATURE_COLS]

    # Fatigue probability (class 1 = high fatigue)
    proba = _pipeline.predict_proba(X)[0][1]
    pred  = int(proba >= 0.5)

    if proba < 0.4:
        status = "nominal"
    elif proba < 0.7:
        status = "moderate"
    else:
        status = "high"

    # SHAP for this individual vector
    scaler   = _pipeline.named_steps["scaler"]
    X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURE_COLS)
    sv       = _explainer.shap_values(X_scaled)

    # For binary RF: sv is [class0_shap, class1_shap], each shape (1, n_features)
    # Extract class-1 SHAP values as a flat list
    if isinstance(sv, list):
        sv1_raw = sv[1][0]
    else:
        sv1_raw = sv[0]

    # Flatten any nested lists/arrays
    sv1 = []
    for v in sv1_raw:
        if hasattr(v, '__iter__'):
            sv1.append(float(list(v)[0]))
        else:
            sv1.append(float(v))

    # Top 3 by |SHAP value|
    shap_pairs = sorted(
        zip(FEATURE_COLS, sv1),
        key=lambda x: abs(x[1]),
        reverse=True
    )[:3]

    shap_top3 = [
        {
            "feature":   feat,
            "label":     FEATURE_LABELS.get(feat, feat),
            "shap_value": round(val, 4),
            "direction": "increases_fatigue" if val > 0 else "reduces_fatigue",
        }
        for feat, val in shap_pairs
    ]

    return {
        "fatigue_score": round(float(proba), 4),
        "fatigue_class": pred,
        "status":        status,
        "shap_top3":     shap_top3,
    }


def score_batch(vectors: list[dict]) -> list[dict]:
    """Score a batch of feature vectors. Returns one result per vector."""
    return [score_vector(v) for v in vectors]


if __name__ == "__main__":
    # Quick test — run after training
    test_vector_low = {
        "iki_mean": 180, "iki_std": 40, "hold_mean": 75,
        "error_rate": 0.02, "key_count": 80,
        "scroll_velocity": 300, "direction_reversals": 2,
        "scroll_event_count": 15, "tab_switches": 3,
        "hour_of_day": 14, "day_of_week": 2,
    }
    test_vector_high = {
        "iki_mean": 290, "iki_std": 95, "hold_mean": 110,
        "error_rate": 0.12, "key_count": 20,
        "scroll_velocity": 950, "direction_reversals": 12,
        "scroll_event_count": 60, "tab_switches": 18,
        "hour_of_day": 23, "day_of_week": 0,
    }

    print("Low fatigue vector:")
    r = score_vector(test_vector_low)
    print(f"  Score: {r['fatigue_score']} | Status: {r['status']}")
    for s in r['shap_top3']:
        print(f"  {s['label']}: {s['shap_value']} ({s['direction']})")

    print("\nHigh fatigue vector:")
    r = score_vector(test_vector_high)
    print(f"  Score: {r['fatigue_score']} | Status: {r['status']}")
    for s in r['shap_top3']:
        print(f"  {s['label']}: {s['shap_value']} ({s['direction']})")
