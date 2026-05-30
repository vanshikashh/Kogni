"""
Kogni Auto Scorer
=================
Runs continuously. Scores every 30 minutes automatically.
Keeps today's bar updated throughout the day.

Run: python auto_score.py
Stop: Ctrl+C
"""

import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

SCORE_INTERVAL = 1800  # 30 minutes
SCRIPT_DIR = Path(__file__).parent
SCORE_SCRIPT = SCRIPT_DIR / "score_now.py"


def run_scorer():
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] Scoring...", end=" ", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, str(SCORE_SCRIPT)],
            capture_output=True, text=True,
            cwd=str(SCRIPT_DIR)
        )
        # Show only key results
        for line in result.stdout.split("\n"):
            if "RF:" in line or "LSTM:" in line:
                print(line.strip(), end=" ")
        if result.returncode == 0:
            print("✓")
        else:
            print(f"ERROR: {result.stderr[:100]}")
    except Exception as e:
        print(f"FAILED: {e}")


def main():
    print("=" * 50)
    print("KOGNI AUTO SCORER")
    print("=" * 50)
    print(f"Scoring every 30 minutes.")
    print(f"Today's bar updates automatically.")
    print(f"Dashboard: http://localhost:3000")
    print(f"Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    # Score immediately on start
    run_scorer()

    last_score = time.time()

    while True:
        time.sleep(60)  # check every minute
        elapsed = time.time() - last_score

        # Score every 30 minutes
        if elapsed >= SCORE_INTERVAL:
            run_scorer()
            last_score = time.time()
        else:
            remaining = int((SCORE_INTERVAL - elapsed) / 60)
            # Show countdown every 10 minutes
            if remaining % 10 == 0 and remaining > 0:
                print(f"  Next score in {remaining} min...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKogni scorer stopped.")
