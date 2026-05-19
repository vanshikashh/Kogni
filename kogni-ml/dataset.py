"""
Kogni Dataset Loader
====================
Maps the Dartmouth CES dataset (phone behavioral features)
to Kogni's browser extension feature space.

Download the CES dataset from:
https://github.com/dartmouth-cs98-23f/project-short-description
Or the OSF repository linked in arXiv:2503.08002

Expected CSV columns (CES dataset):
    - screen_on_count     → key_count proxy
    - session_duration    → window_duration_s
    - app_switch_count    → tab_switches
    - night_usage         → hour_of_day proxy
    - phq_score           → mental_health_label (our target)
    ... (varies by CES version)

This loader also generates SYNTHETIC training data when the
real CES dataset is not yet available — letting you train
and validate the pipeline before any real users exist.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from features import FEATURE_COLS, FEATURE_DEFAULTS


def load_ces_dataset(path: str) -> tuple[pd.DataFrame, pd.Series]:
    """
    Load and map the Dartmouth CES dataset to Kogni features.
    Returns (X, y) where y is binary: 1=high_cognitive_load, 0=low.
    """
    df = pd.read_csv(path)

    # Map CES columns → Kogni features
    # Adjust column names to match your CES CSV version
    mapped = pd.DataFrame()

    # IKI proxy: phone unlock → type session rhythm
    # CES doesn't have keystroke data; we use screen session patterns
    mapped["iki_mean"]     = df.get("avg_session_duration", pd.Series(dtype=float)) * 0.8 + 100
    mapped["iki_std"]      = df.get("std_session_duration", pd.Series(dtype=float)) * 0.3 + 30
    mapped["hold_mean"]    = 80.0  # constant proxy
    mapped["error_rate"]   = df.get("unlock_count", pd.Series(dtype=float)) / 500

    mapped["key_count"]          = df.get("unlock_count", pd.Series(dtype=float)) * 10
    mapped["scroll_velocity"]    = df.get("screen_on_duration", pd.Series(dtype=float)) * 2 + 200
    mapped["direction_reversals"] = df.get("app_switch_count", pd.Series(dtype=float)) * 0.3
    mapped["scroll_event_count"] = df.get("screen_on_duration", pd.Series(dtype=float)) * 5
    mapped["tab_switches"]       = df.get("app_switch_count", pd.Series(dtype=float))
    mapped["hour_of_day"]        = df.get("hour_of_day", pd.Series(dtype=float))
    mapped["day_of_week"]        = df.get("day_of_week", pd.Series(dtype=float))

    # Fill defaults for missing columns
    for col, default in FEATURE_DEFAULTS.items():
        if col not in mapped or mapped[col].isna().all():
            mapped[col] = default
        else:
            mapped[col] = mapped[col].fillna(default)

    mapped = mapped[FEATURE_COLS]

    # Target: PHQ-9 score > 10 = high cognitive load
    phq = df.get("phq_score", df.get("phq9_score", None))
    if phq is None:
        raise ValueError("PHQ score column not found in CES dataset. Check column names.")

    y = (phq > 10).astype(int)
    return mapped, y


def generate_synthetic_data(
    n_samples: int = 2000,
    seed: int = 42
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Generate synthetic training data based on research-validated
    feature distributions from published literature.

    Feature ranges from:
    - PMC10296416 (keystroke dynamics in cognitive assessment)
    - AIJFR 2025 (keystroke fatigue prediction)
    - arXiv:2503.08002 (Dartmouth CES behavioral distributions)

    HIGH cognitive load (fatigue=1) pattern:
        - High IKI mean (slower, more hesitant typing)
        - High IKI std (irregular, fragmented rhythm)
        - High error rate (more backspaces)
        - High scroll velocity (fast, unfocused scrolling)
        - High tab switches (context fragmentation)
        - Late hour_of_day (23:00+ usage)

    LOW cognitive load (fatigue=0) pattern:
        - Lower IKI mean (fluid typing)
        - Lower IKI std (consistent rhythm)
        - Low error rate
        - Moderate scroll velocity
        - Lower tab switches
        - Daytime hours
    """
    rng = np.random.default_rng(seed)
    n0 = n_samples // 2  # low fatigue
    n1 = n_samples - n0  # high fatigue

    def make_class(n, is_high):
        m = 1 if is_high else 0
        d = {}
        d["iki_mean"]            = rng.normal(220 + 60*m,  30, n)
        d["iki_std"]             = rng.normal(60  + 30*m,  15, n)
        d["hold_mean"]           = rng.normal(90  + 20*m,  20, n)
        d["error_rate"]          = rng.beta(1+3*m, 20, n) * 0.3
        d["key_count"]           = rng.integers(5,  150 - 60*m, n).astype(float)
        d["scroll_velocity"]     = rng.normal(400 + 300*m, 100, n)
        d["direction_reversals"] = rng.poisson(2 + 6*m, n).astype(float)
        d["scroll_event_count"]  = rng.integers(0, 50 + 40*m, n).astype(float)
        d["tab_switches"]        = rng.poisson(3 + 8*m, n).astype(float)
        # Late-night usage strongly predicts high fatigue
        probs_low  = [0.02]*6 + [0.04]*6 + [0.05]*6 + [0.03]*3 + [0.04]*3
        probs_high = [0.02]*6 + [0.02]*6 + [0.04]*6 + [0.06]*3 + [0.10]*3
        # Normalize to ensure sum=1
        def norm(p): s=sum(p); return [x/s for x in p]
        d["hour_of_day"] = rng.choice(range(24), p=norm(probs_low if not is_high else probs_high), size=n).astype(float)
        d["day_of_week"]         = rng.integers(0, 7, n).astype(float)
        return pd.DataFrame(d)

    X = pd.concat([make_class(n0, False), make_class(n1, True)], ignore_index=True)
    y = pd.Series([0]*n0 + [1]*n1, name="fatigue")

    # Clip to realistic ranges
    X["iki_mean"]        = X["iki_mean"].clip(80, 500)
    X["iki_std"]         = X["iki_std"].clip(10, 200)
    X["error_rate"]      = X["error_rate"].clip(0, 0.5)
    X["scroll_velocity"] = X["scroll_velocity"].clip(50, 2000)

    # Shuffle
    idx = rng.permutation(len(X))
    return X.iloc[idx][FEATURE_COLS].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)


if __name__ == "__main__":
    X, y = generate_synthetic_data(2000)
    print(f"Generated {len(X)} samples")
    print(f"Class balance: {y.value_counts().to_dict()}")
    print(f"\nFeature stats:")
    print(X.describe().round(2))
