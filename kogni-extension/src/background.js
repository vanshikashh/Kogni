/**
 * Kogni Background Service Worker
 *
 * Responsibilities:
 *  - Receive feature vectors from content scripts
 *  - Track tab switch frequency (cross-tab signal)
 *  - Batch vectors and flush to the Kogni API
 *  - Store JWT token securely in chrome.storage.local
 *  - Update extension badge with latest fatigue score
 */

const API_BASE = "http://localhost:8000"; // swap to https://api.kogni.app in prod
const FLUSH_INTERVAL_MS = 60_000;         // flush batch every 60 seconds
const MAX_BATCH_SIZE = 10;

// ─── In-memory state ─────────────────────────────────────────────────────────

let vectorBatch = [];
let tabSwitchCount = 0;
let lastTabSwitchTs = Date.now();
let tabSwitchesInWindow = 0;

// ─── Tab switch tracking ──────────────────────────────────────────────────────

chrome.tabs.onActivated.addListener(() => {
  tabSwitchCount++;
  tabSwitchesInWindow++;
});

// ─── Message handler (from content scripts) ───────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "FEATURE_VECTOR") {
    const vector = {
      ...message.payload,
      tab_switches: tabSwitchesInWindow,
    };

    tabSwitchesInWindow = 0; // reset window count after attaching

    vectorBatch.push(vector);

    // Flush early if batch is full
    if (vectorBatch.length >= MAX_BATCH_SIZE) {
      flushBatch();
    }
  }

  if (message.type === "GET_BADGE_STATE") {
    sendResponse({ score: currentFatigueScore });
  }

  if (message.type === "SET_TOKEN") {
    chrome.storage.local.set({ kogni_token: message.token });
  }

  if (message.type === "CLEAR_TOKEN") {
    chrome.storage.local.remove("kogni_token");
    updateBadge(null);
  }
});

// ─── Batch flush ──────────────────────────────────────────────────────────────

async function flushBatch() {
  if (vectorBatch.length === 0) return;

  const token = await getToken();
  if (!token) return; // not authenticated, drop batch silently

  const batch = [...vectorBatch];
  vectorBatch = []; // clear before await so new vectors aren't lost

  try {
    const res = await fetch(`${API_BASE}/api/v1/events/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ vectors: batch }),
    });

    if (res.status === 401) {
      // Token expired — clear it, user needs to re-auth
      chrome.storage.local.remove("kogni_token");
      updateBadge(null);
      return;
    }

    if (res.ok) {
      const data = await res.json();
      // API may return latest fatigue score with ingestion response
      if (data.fatigue_score !== undefined) {
        updateBadge(data.fatigue_score);
      }
    }
  } catch (err) {
    // Network error — put batch back (prepend to preserve order)
    vectorBatch = [...batch, ...vectorBatch];
    console.error("[Kogni] Flush failed:", err.message);
  }
}

// ─── Badge management ─────────────────────────────────────────────────────────

let currentFatigueScore = null;

function updateBadge(score) {
  currentFatigueScore = score;

  if (score === null) {
    chrome.action.setBadgeText({ text: "" });
    return;
  }

  // Score is 0–1. Thresholds: green < 0.4, amber < 0.7, red >= 0.7
  let color, label;

  if (score < 0.4) {
    color = "#1D9E75";  // teal — good
    label = "OK";
  } else if (score < 0.7) {
    color = "#EF9F27";  // amber — moderate fatigue
    label = "~";
  } else {
    color = "#E24B4A";  // red — high fatigue
    label = "!";
  }

  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setBadgeText({ text: label });
}

// ─── Scheduled flush via alarms ───────────────────────────────────────────────

chrome.alarms.create("kogni-flush", { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "kogni-flush") {
    flushBatch();
  }
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getToken() {
  return new Promise((resolve) => {
    chrome.storage.local.get("kogni_token", (result) => {
      resolve(result.kogni_token || null);
    });
  });
}
