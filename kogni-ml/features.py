"""
Kogni feature definitions.
Single source of truth for feature names and order —
used by both the training pipeline and the inference worker.
"""

# The exact feature vector the Chrome extension sends
# and that the RF model expects as input.
FEATURE_COLS = [
    "iki_mean",           # inter-key interval mean (ms)
    "iki_std",            # inter-key interval std dev (ms)
    "hold_mean",          # key hold duration mean (ms)
    "error_rate",         # backspace / total keys
    "key_count",          # total keystrokes in window
    "scroll_velocity",    # avg scroll speed (px/sec)
    "direction_reversals",# scroll direction changes
    "scroll_event_count", # total scroll events
    "tab_switches",       # tab context switches in window
    "hour_of_day",        # 0–23
    "day_of_week",        # 0=Mon … 6=Sun
]

# Human-readable names for SHAP insight cards
FEATURE_LABELS = {
    "iki_mean":            "Keystroke speed (IKI)",
    "iki_std":             "Typing rhythm consistency",
    "hold_mean":           "Key hold duration",
    "error_rate":          "Error / backspace rate",
    "key_count":           "Typing activity volume",
    "scroll_velocity":     "Scroll speed",
    "direction_reversals": "Scroll direction changes",
    "scroll_event_count":  "Scroll activity volume",
    "tab_switches":        "Tab context switching",
    "hour_of_day":         "Time of day",
    "day_of_week":         "Day of week",
}

# Default fill values when a feature is missing
FEATURE_DEFAULTS = {
    "iki_mean": 200.0,
    "iki_std": 50.0,
    "hold_mean": 80.0,
    "error_rate": 0.05,
    "key_count": 0,
    "scroll_velocity": 300.0,
    "direction_reversals": 0,
    "scroll_event_count": 0,
    "tab_switches": 0,
    "hour_of_day": 12,
    "day_of_week": 0,
}
