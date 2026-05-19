"""
Kogni Recovery Engine
=====================
Detects when a user needs a cognitive recovery intervention
and measures whether their rhythm has returned to baseline
after completing a typing exercise.

Research basis:
  - PMC9010884: Attention Restoration Theory — structured rest
    restores attentional resources depleted by cognitive fatigue
  - arXiv:2501.15583: Typing metrics as continuous cognitive
    performance proxy — rhythm return = recovery signal
  - AIJFR 2025: IKI as reliable fatigue biomarker

How it works:
  1. Trigger: fatigue_score > 0.75 for N consecutive readings
  2. Task: user types a 40-word passage at natural pace
  3. Measurement: post-task IKI vs user's 7-day baseline IKI
  4. Recovery confirmed: post IKI within 15% of baseline
"""

import json
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional


# ── Recovery passages ─────────────────────────────────────
# Chosen to be neutral, moderate length, no emotional loading
# Each ~40 words to give enough keystrokes for IKI measurement

RECOVERY_PASSAGES = [
    "The system quietly observes how you type and scroll. It builds a picture of your cognitive rhythm over time. When that rhythm shifts, it notices. This exercise helps it measure where you are right now.",

    "Focus is not a switch you flip. It builds slowly and depletes faster than most people realize. Taking a short pause to type at your natural pace gives your attention a moment to reset.",

    "Every keystroke carries timing information. The gaps between keys, the hesitations, the small corrections — all of these form a pattern unique to you. That pattern changes when your mind is tired.",

    "Cognitive health is not visible the way physical health sometimes is. But it leaves traces in behavior. The way you type when you are sharp is different from the way you type when you are not.",

    "A few minutes of deliberate, unhurried typing can help restore the rhythm that sustained focus requires. There is no rush here. Type at whatever pace feels natural to you right now.",
]


class RecoveryEngine:
    """
    Manages the full recovery intervention cycle for a user.
    """

    FATIGUE_THRESHOLD     = 0.75   # score above this triggers intervention
    CONSECUTIVE_REQUIRED  = 3      # readings in a row above threshold
    RECOVERY_TOLERANCE    = 0.15   # 15% of baseline = recovered
    MIN_KEYSTROKES        = 30     # minimum for reliable IKI measurement

    def __init__(self, db_session, user_id: int):
        self.db      = db_session
        self.user_id = user_id

    def get_baseline_iki(self) -> Optional[float]:
        """
        Compute the user's personal baseline IKI from the last 7 days.
        This is the reference point for recovery measurement.
        """
        from sqlalchemy import text
        since = datetime.now(timezone.utc) - timedelta(days=7)
        row = self.db.execute(text("""
            SELECT AVG(iki_mean), COUNT(*)
            FROM feature_vectors
            WHERE user_id = :uid
              AND ts >= :since
              AND iki_mean IS NOT NULL
              AND key_count > 5
        """), {"uid": self.user_id, "since": since}).fetchone()

        if not row or row[1] < 3:  # need at least 3 windows
            return None
        return float(row[0])

    def should_trigger(self, recent_scores: list[float]) -> bool:
        """
        Returns True if fatigue has been high for CONSECUTIVE_REQUIRED readings.
        """
        if len(recent_scores) < self.CONSECUTIVE_REQUIRED:
            return False
        last_n = recent_scores[-self.CONSECUTIVE_REQUIRED:]
        return all(s >= self.FATIGUE_THRESHOLD for s in last_n)

    def get_passage(self, user_id: int) -> dict:
        """Return a passage — rotates based on user_id and day."""
        idx = (user_id + datetime.now().day) % len(RECOVERY_PASSAGES)
        return {
            "passage_id": idx,
            "text":       RECOVERY_PASSAGES[idx],
            "word_count": len(RECOVERY_PASSAGES[idx].split()),
        }

    def measure_recovery(
        self,
        keystroke_timings: list[int],   # raw keydown timestamps in ms
        baseline_iki: Optional[float],
    ) -> dict:
        """
        Analyze post-exercise keystroke timings to determine recovery.

        Args:
            keystroke_timings: list of keydown timestamps (ms since epoch)
            baseline_iki: user's personal 7-day mean IKI in ms

        Returns:
            {
                post_iki_mean: float,
                post_iki_std:  float,
                keystrokes:    int,
                recovered:     bool,
                pct_of_baseline: float | None,
                message:       str,
            }
        """
        if len(keystroke_timings) < self.MIN_KEYSTROKES:
            return {
                "post_iki_mean":     None,
                "post_iki_std":      None,
                "keystrokes":        len(keystroke_timings),
                "recovered":         False,
                "pct_of_baseline":   None,
                "message":           f"Not enough keystrokes ({len(keystroke_timings)}/{self.MIN_KEYSTROKES}). Try typing more.",
            }

        # Compute IKIs from raw timestamps
        timings = sorted(keystroke_timings)
        ikis = [timings[i] - timings[i-1] for i in range(1, len(timings))
                if 50 < timings[i] - timings[i-1] < 3000]

        if not ikis:
            return {
                "post_iki_mean": None, "post_iki_std": None,
                "keystrokes": len(keystroke_timings),
                "recovered": False, "pct_of_baseline": None,
                "message": "Could not compute IKI — timing data invalid.",
            }

        post_iki_mean = float(np.mean(ikis))
        post_iki_std  = float(np.std(ikis))

        # Recovery decision
        recovered        = False
        pct_of_baseline  = None
        message          = ""

        if baseline_iki is None:
            # No baseline yet — just record and mark as recovered
            # (can't compare without reference)
            recovered = True
            message   = "No baseline yet — rhythm recorded as new baseline."
        else:
            pct_of_baseline = abs(post_iki_mean - baseline_iki) / baseline_iki
            if pct_of_baseline <= self.RECOVERY_TOLERANCE:
                recovered = True
                message   = f"Rhythm restored — within {pct_of_baseline*100:.1f}% of your baseline."
            else:
                recovered = False
                message   = f"Still elevated — {pct_of_baseline*100:.1f}% above baseline. Consider a longer break."

        return {
            "post_iki_mean":   round(post_iki_mean, 2),
            "post_iki_std":    round(post_iki_std, 2),
            "keystrokes":      len(keystroke_timings),
            "recovered":       recovered,
            "pct_of_baseline": round(pct_of_baseline, 4) if pct_of_baseline is not None else None,
            "message":         message,
        }

    def log_intervention(
        self,
        pre_score:    float,
        post_result:  dict,
        passage_id:   int,
    ) -> int:
        """Write intervention record to DB. Returns intervention ID."""
        from sqlalchemy import text
        result = self.db.execute(text("""
            INSERT INTO interventions
                (user_id, triggered_at, pre_score, post_iki_mean,
                 post_iki_std, keystrokes, recovered, passage_id)
            VALUES
                (:uid, :ts, :pre, :post_iki, :post_std, :ks, :rec, :pid)
        """), {
            "uid":      self.user_id,
            "ts":       datetime.now(timezone.utc).isoformat(),
            "pre":      pre_score,
            "post_iki": post_result.get("post_iki_mean"),
            "post_std": post_result.get("post_iki_std"),
            "ks":       post_result.get("keystrokes"),
            "rec":      1 if post_result.get("recovered") else 0,
            "pid":      passage_id,
        })
        self.db.commit()
        return result.lastrowid
