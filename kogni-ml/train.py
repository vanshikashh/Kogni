"""
Kogni RF Trainer
================
Trains the Random Forest cognitive fatigue classifier.

Research basis:
  - AIJFR 2025: RF achieved 89% accuracy on keystroke fatigue
  - arXiv:2503.08002: interpretable ML on Dartmouth CES (XGBoost + SHAP)
  - PMC10296416: keystroke dynamics as cognitive biomarker

Usage:
    python train.py                          # uses synthetic data
    python train.py --ces /path/to/ces.csv  # uses real CES dataset
"""

import argparse
import json
import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report, confusion_matrix
)
from sklearn.pipeline import Pipeline

from features import FEATURE_COLS, FEATURE_LABELS
from dataset import generate_synthetic_data, load_ces_dataset

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


def train(use_ces: str | None = None):
    print("=" * 60)
    print("KOGNI RF TRAINER")
    print("=" * 60)

    # ── Load data ──────────────────────────────────────────
    if use_ces:
        print(f"\n[DATA] Loading CES dataset: {use_ces}")
        X, y = load_ces_dataset(use_ces)
    else:
        print("\n[DATA] Using synthetic training data")
        print("       (swap for CES dataset when available)")
        X, y = generate_synthetic_data(n_samples=3000, seed=42)

    print(f"       Samples: {len(X)} | High fatigue: {y.sum()} | Low: {(y==0).sum()}")

    # ── Train / test split ────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # ── Model pipeline ────────────────────────────────────
    # RandomForest is interpretable via SHAP and fast for real-time inference.
    # No scaling needed for RF, but we include it for future model swaps.
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=4,
        max_features="sqrt",
        class_weight="balanced",  # handles any class imbalance
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  rf),
    ])

    print("\n[TRAIN] Fitting RandomForest (200 estimators)...")
    pipeline.fit(X_train, y_train)

    # ── Evaluation ────────────────────────────────────────
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec  = recall_score(y_test, y_pred)
    f1   = f1_score(y_test, y_pred)
    auc  = roc_auc_score(y_test, y_prob)

    print(f"\n[EVAL] Test set results:")
    print(f"       Accuracy:  {acc:.4f}  (benchmark: 0.89 from AIJFR 2025)")
    print(f"       Precision: {prec:.4f}")
    print(f"       Recall:    {rec:.4f}")
    print(f"       F1:        {f1:.4f}")
    print(f"       ROC-AUC:   {auc:.4f}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['low_fatigue','high_fatigue'])}")

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
    print(f"[CV]   5-fold ROC-AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # ── SHAP explainability ───────────────────────────────
    print("\n[SHAP] Computing global feature importance...")

    # SHAP TreeExplainer works directly on the RF (inside the pipeline)
    rf_model = pipeline.named_steps["model"]
    scaler   = pipeline.named_steps["scaler"]
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test),
        columns=FEATURE_COLS
    )

    explainer   = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_test_scaled)

    # shap_values is [class0, class1] for binary RF
    sv_class1 = shap_values[1] if isinstance(shap_values, list) else shap_values

    # Global mean |SHAP| per feature
    mean_shap = np.abs(sv_class1).mean(axis=0)
    # Ensure mean_shap is a 1D numpy array of scalars
    if hasattr(mean_shap, 'tolist'):
        mean_shap_list = mean_shap.tolist()
        if isinstance(mean_shap_list[0], list):
            mean_shap_list = [v[0] if isinstance(v, list) else v for v in mean_shap_list]
    else:
        mean_shap_list = list(mean_shap)
    feature_importance = dict(zip(FEATURE_COLS, mean_shap_list))
    ranked = sorted(feature_importance.items(), key=lambda x: float(x[1]), reverse=True)

    print("\n       Global SHAP feature importance (mean |SHAP|):")
    for feat, val in ranked:
        val_f = float(val)
        bar = "█" * max(0, int(val_f * 100))
        label = FEATURE_LABELS.get(feat, feat)
        print(f"       {label:<35} {val_f:.4f}  {bar}")

    # ── Save artefacts ────────────────────────────────────
    joblib.dump(pipeline, MODEL_DIR / "rf_pipeline.joblib")
    joblib.dump(explainer, MODEL_DIR / "shap_explainer.joblib")

    metadata = {
        "feature_cols":  FEATURE_COLS,
        "accuracy":      round(acc, 4),
        "precision":     round(prec, 4),
        "recall":        round(rec, 4),
        "f1":            round(f1, 4),
        "roc_auc":       round(auc, 4),
        "cv_auc_mean":   round(cv_scores.mean(), 4),
        "cv_auc_std":    round(cv_scores.std(), 4),
        "feature_importance": {k: round(v, 4) for k, v in feature_importance.items()},
        "top_3_features": [feat for feat, _ in ranked[:3]],
        "trained_on": "synthetic" if not use_ces else use_ces,
        "n_train": len(X_train),
        "n_test":  len(X_test),
    }
    with open(MODEL_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[SAVE] rf_pipeline.joblib    → {MODEL_DIR}/")
    print(f"[SAVE] shap_explainer.joblib → {MODEL_DIR}/")
    print(f"[SAVE] metadata.json         → {MODEL_DIR}/")
    print(f"\n✓ Training complete. Model ready for inference.")
    return pipeline, explainer, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ces", type=str, default=None,
                        help="Path to CES dataset CSV")
    args = parser.parse_args()
    train(use_ces=args.ces)
