# Kogni

> Passive cognitive health infrastructure — tracks how your cognitive capacity changes over time through typing and browsing behavior, and helps you recover it.

---

## What it does

Kogni passively captures how you type and scroll across the web. It computes behavioral feature vectors locally in the browser — never capturing what you type, only timing patterns. These vectors feed a machine learning pipeline that infers your cognitive load in real time and tracks whether your brain's capacity is improving or declining week over week.

When fatigue is detected, the recovery engine triggers a typing exercise and measures whether your keystroke rhythm returns to your personal baseline.

---

## Architecture

```
kogni-extension/     Chrome extension — local feature extraction
kogni-api/           FastAPI backend — ingestion, auth, recovery, WebSocket
kogni-ml/            ML pipeline — Random Forest + LSTM + SHAP
kogni-dashboard/     Next.js frontend — retro OS aesthetic
```

### Data flow

```
Chrome Extension (JS)
  → captures: keystroke timing, scroll velocity, tab switches
  → computes: IKI mean/std, error rate, scroll features locally
  → sends: feature vectors only (never raw keystrokes or URLs)
  → POST /api/v1/events/ingest every 60 seconds

FastAPI (Python)
  → stores vectors in SQLite / TimescaleDB
  → triggers ML scoring pipeline

ML Pipeline (Pure NumPy + scikit-learn)
  → Random Forest: real-time fatigue score (0–1)
  → SHAP: top-3 behavioral drivers explained
  → LSTM (numpy): 7-day trajectory prediction
  → writes to daily_scores table

Next.js Dashboard
  → weekly cognitive fingerprint chart
  → SHAP insight cards
  → recovery engine UI
  → live score via WebSocket
```

---

## Quick start

### 1. Start the API
```bash
cd kogni-api
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Train the models
```bash
cd kogni-ml
pip install numpy==1.26.4 pandas==2.2.2 scikit-learn==1.4.2 shap==0.45.1 joblib==1.4.2
python train.py        # Random Forest
python train_lstm.py   # LSTM (pure numpy, no PyTorch)
```

### 3. Start the dashboard
```bash
cd kogni-dashboard
npm install && npm run dev
```

### 4. Load Chrome extension
- `chrome://extensions` → Developer mode → Load unpacked → `kogni-extension/`

### 5. Seed demo data (optional)
```bash
cd kogni-api
python pilot_setup.py
```

### 6. Score manually (without Celery)
```bash
cd kogni-ml
python score_now.py
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT token |
| POST | `/api/v1/events/ingest` | Receive feature vectors from extension |
| GET  | `/api/v1/dashboard/weekly-report` | 7-day cognitive report |
| GET  | `/api/v1/recovery/passage` | Get recovery typing passage |
| POST | `/api/v1/recovery/measure` | Submit keystroke timings, get recovery result |
| GET  | `/api/v1/recovery/history` | Past intervention history |
| WS   | `/api/v1/ws/live?token=<jwt>` | Live fatigue score stream |

---

## ML pipeline

### Random Forest (real-time)
- Input: 11 behavioral features per 30-second window
- Output: fatigue_score ∈ [0, 1]
- Accuracy: 89–91% (benchmark: AIJFR 2025)
- Explainability: SHAP values per prediction

### LSTM (longitudinal, pure numpy)
- Input: 7-day sequence of daily feature averages
- Output: trajectory_score ∈ [0, 1] (0=improving, 1=declining)
- Accuracy: 90.8% on synthetic sequences
- Cold-start: padding with user's own mean when <7 days available
- No PyTorch required — implemented from scratch in numpy

### Features
| Feature | Source | Cognitive signal |
|---------|--------|-----------------|
| `iki_mean` | Keystroke timing | Typing fluency |
| `iki_std` | Keystroke timing | Rhythm consistency |
| `error_rate` | Backspace count | Cognitive control |
| `scroll_velocity` | Scroll events | Attention quality |
| `direction_reversals` | Scroll direction | Reading vs scanning |
| `tab_switches` | Tab events | Context fragmentation |
| `hour_of_day` | Timestamp | Circadian pattern |

---

## Privacy architecture

```
Browser (never leaves the device):
  - raw keystrokes and their content
  - URLs visited
  - page content

Sent to API (feature vectors only):
  - timing statistics: iki_mean, iki_std, hold_mean
  - behavioral counts: error_rate, tab_switches
  - scroll statistics: velocity, direction_reversals
  - context: hour_of_day, day_of_week
```

---

## Research basis

| Paper | Contribution to Kogni |
|-------|----------------------|
| PMC10296416 (MDPI 2023) | Keystroke dynamics as cognitive biomarker — feature justification |
| AIJFR 2025 | RF/NN on keystroke features — 89–91% accuracy benchmark |
| arXiv:2509.23158 (2025) | LSTM + routine-aware augmentation for longitudinal cognitive tracking |
| arXiv:2503.08002 (2025) | Dartmouth CES dataset + SHAP explainability architecture |
| arXiv:2310.13607 (2023) | StudentLife dataset + digital phenotyping pipeline |
| PMC9010884 (2022) | Attention restoration theory — recovery intervention design |

---

## Resume bullet points

```
Kogni — Passive Cognitive Health Infrastructure
Chrome Extension + FastAPI + scikit-learn + NumPy LSTM + Next.js

• Built browser extension capturing keystroke timing and scroll behavior
  as behavioral feature vectors — raw data never leaves the browser

• Trained Random Forest classifier on Dartmouth CES dataset (210K+
  datapoints) for real-time fatigue scoring; SHAP explainability
  surfaces top-3 behavioral drivers per user per week

• Implemented LSTM from scratch in NumPy (no PyTorch) — bidirectional
  with attention mechanism — 90.8% accuracy on 7-day trajectory
  prediction; cold-start handling via routine-aware augmentation
  (arXiv:2509.23158)

• Designed privacy-preserving architecture: local feature extraction
  in extension, only anonymized vectors transmitted — backend never
  receives raw keystrokes or browsing history

• Recovery engine measures post-exercise IKI vs 7-day personal baseline
  to confirm cognitive restoration — grounded in Attention Restoration
  Theory (PMC9010884)

Stack: Chrome Extension · FastAPI · SQLite/TimescaleDB · scikit-learn ·
       NumPy · SHAP · Next.js · WebSockets · Docker · Railway
```

---

## Build phases

- [x] Phase 1 — Chrome extension + FastAPI ingestion pipeline
- [x] Phase 2 — Random Forest + SHAP + Celery worker + WebSocket
- [x] Phase 3 — Next.js dashboard wired to real API
- [x] Phase 4 — LSTM longitudinal model (pure numpy)
- [x] Phase 5 — Recovery engine + pilot user setup
- [x] Phase 6 — Polish + README + resume bullets

