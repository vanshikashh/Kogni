/**
 * Kogni Background Service Worker — Fixed
 *
 * Fixes:
 * 1. Never auto-delete token on 401 (was causing token wipe loop)
 * 2. chrome.alarms.create inside onInstalled for MV3 reliability
 * 3. Better error logging so you can see what's happening
 */

const API_BASE        = "http://localhost:8000";
const FLUSH_INTERVAL  = 1;       // minutes
const MAX_BATCH_SIZE  = 10;

let vectorBatch          = [];
let tabSwitchesInWindow  = 0;
let currentFatigueScore  = null;

// ── Tab switch tracking ───────────────────────────────────
chrome.tabs.onActivated.addListener(() => {
  tabSwitchesInWindow++;
});

// ── Setup alarm on install (MV3 best practice) ────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("kogni-flush", { periodInMinutes: FLUSH_INTERVAL });
  console.log("[Kogni] Installed. Flush alarm created.");
});

// Also create alarm on startup in case service worker restarts
chrome.alarms.get("kogni-flush", (alarm) => {
  if (!alarm) {
    chrome.alarms.create("kogni-flush", { periodInMinutes: FLUSH_INTERVAL });
  }
});

// ── Message handler ───────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "FEATURE_VECTOR") {
    const vector = {
      ...message.payload,
      tab_switches: tabSwitchesInWindow,
    };
    tabSwitchesInWindow = 0;
    vectorBatch.push(vector);
    console.log("[Kogni] Vector received. Batch size:", vectorBatch.length);

    if (vectorBatch.length >= MAX_BATCH_SIZE) {
      flushBatch();
    }
  }

  if (message.type === "GET_BADGE_STATE") {
    sendResponse({ score: currentFatigueScore });
    return true;
  }
});

// ── Flush batch to API ────────────────────────────────────
async function flushBatch() {
  if (vectorBatch.length === 0) {
    console.log("[Kogni] Nothing to flush.");
    return;
  }

  const token = await getToken();
  if (!token) {
    console.warn("[Kogni] No token set — skipping flush. Set token via service worker console.");
    return;
  }

  const batch   = [...vectorBatch];
  vectorBatch   = [];

  console.log(`[Kogni] Flushing ${batch.length} vectors...`);

  try {
    const res = await fetch(`${API_BASE}/api/v1/events/ingest`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ vectors: batch }),
    });

    if (res.status === 401) {
      // ✅ FIXED: Do NOT clear token on 401.
      // Token may be temporarily invalid due to API restart.
      // Just log and keep the token so user doesn't have to reset it.
      console.error("[Kogni] 401 Unauthorized. Check if API is running and token is current.");
      vectorBatch = [...batch, ...vectorBatch]; // restore batch
      return;
    }

    if (res.ok) {
      const data = await res.json();
      console.log(`[Kogni] Flush OK. Accepted: ${data.accepted}. Total: ${data.total_vectors}`);
      if (data.fatigue_score != null) {
        updateBadge(data.fatigue_score);
      }
    } else {
      console.error("[Kogni] Flush failed:", res.status, res.statusText);
      vectorBatch = [...batch, ...vectorBatch];
    }

  } catch (err) {
    console.error("[Kogni] Network error:", err.message);
    vectorBatch = [...batch, ...vectorBatch];
  }
}

// ── Alarm handler ─────────────────────────────────────────
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "kogni-flush") {
    console.log("[Kogni] Alarm fired — flushing...");
    flushBatch();
  }
});

// ── Badge ─────────────────────────────────────────────────
function updateBadge(score) {
  currentFatigueScore = score;
  if (score === null) {
    chrome.action.setBadgeText({ text: "" });
    return;
  }
  const color = score < 0.4 ? "#1D9E75" : score < 0.7 ? "#EF9F27" : "#E24B4A";
  const label = score < 0.4 ? "OK"       : score < 0.7 ? "~"       : "!";
  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setBadgeText({ text: label });
}

// ── Token helper ──────────────────────────────────────────
function getToken() {
  return new Promise((resolve) => {
    chrome.storage.local.get("kogni_token", (result) => {
      resolve(result.kogni_token || null);
    });
  });
}
