/**
 * Kogni Content Script
 *
 * Runs on every page. Captures:
 *   - Keystroke timing (IKI, hold duration, error rate) — NO content ever captured
 *   - Scroll behavior (velocity, direction reversals)
 *   - Session activity signals (idle gaps)
 *
 * All raw events stay local. Only computed feature vectors leave this script.
 */

(() => {
  // ─── State ────────────────────────────────────────────────────────────────

  const WINDOW_MS = 30_000; // 30-second feature window

  let keyEvents = [];       // { downAt, upAt } pairs
  let backspaceCount = 0;
  let totalKeyCount = 0;

  let scrollEvents = [];    // { ts, y } positions
  let lastScrollY = window.scrollY;
  let lastScrollTs = Date.now();

  let windowStart = Date.now();

  // ─── Keystroke capture ────────────────────────────────────────────────────
  // We capture timestamps only. The key value is intentionally NOT recorded
  // for content fields. For backspace we track count only (error rate signal).

  const keyDownMap = new Map(); // keyCode → downAt timestamp

  document.addEventListener("keydown", (e) => {
    keyDownMap.set(e.code, Date.now());
    totalKeyCount++;
    if (e.code === "Backspace") backspaceCount++;
  }, { capture: true, passive: true });

  document.addEventListener("keyup", (e) => {
    const downAt = keyDownMap.get(e.code);
    if (downAt === undefined) return;
    keyDownMap.delete(e.code);

    const upAt = Date.now();
    keyEvents.push({ downAt, upAt });
  }, { capture: true, passive: true });

  // ─── Scroll capture ───────────────────────────────────────────────────────

  document.addEventListener("scroll", () => {
    const ts = Date.now();
    const y = window.scrollY;
    scrollEvents.push({ ts, y });
    lastScrollY = y;
    lastScrollTs = ts;
  }, { capture: true, passive: true });

  // ─── Feature computation ──────────────────────────────────────────────────

  function computeKeystrokeFeatures() {
    if (keyEvents.length < 2) {
      return { iki_mean: null, iki_std: null, hold_mean: null, error_rate: null, key_count: 0 };
    }

    // Inter-key intervals: time between consecutive keydown events
    const ikis = [];
    for (let i = 1; i < keyEvents.length; i++) {
      const gap = keyEvents[i].downAt - keyEvents[i - 1].downAt;
      if (gap > 0 && gap < 5000) ikis.push(gap); // ignore gaps > 5s (user paused)
    }

    // Hold durations: time key was physically held down
    const holds = keyEvents
      .map(e => e.upAt - e.downAt)
      .filter(h => h >= 0 && h < 2000);

    const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
    const std = arr => {
      const m = mean(arr);
      return Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / arr.length);
    };

    return {
      iki_mean: ikis.length ? Math.round(mean(ikis)) : null,       // ms
      iki_std: ikis.length ? Math.round(std(ikis)) : null,          // ms
      hold_mean: holds.length ? Math.round(mean(holds)) : null,     // ms
      error_rate: totalKeyCount > 0
        ? parseFloat((backspaceCount / totalKeyCount).toFixed(4))
        : null,
      key_count: totalKeyCount,
    };
  }

  function computeScrollFeatures() {
    if (scrollEvents.length < 2) {
      return { scroll_velocity: null, direction_reversals: 0, scroll_event_count: 0 };
    }

    // Average scroll velocity (px/sec)
    const velocities = [];
    let reversals = 0;
    let lastDir = null;

    for (let i = 1; i < scrollEvents.length; i++) {
      const dy = scrollEvents[i].y - scrollEvents[i - 1].y;
      const dt = (scrollEvents[i].ts - scrollEvents[i - 1].ts) / 1000; // seconds
      if (dt <= 0) continue;

      const v = Math.abs(dy / dt);
      if (v < 10000) velocities.push(v); // ignore extreme outliers

      const dir = dy > 0 ? "down" : dy < 0 ? "up" : null;
      if (dir && lastDir && dir !== lastDir) reversals++;
      if (dir) lastDir = dir;
    }

    const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;

    return {
      scroll_velocity: velocities.length
        ? Math.round(mean(velocities))
        : null,                                    // px/sec
      direction_reversals: reversals,
      scroll_event_count: scrollEvents.length,
    };
  }

  function buildFeatureVector() {
    const ts = Date.now();
    const elapsed = (ts - windowStart) / 1000; // seconds

    const keystroke = computeKeystrokeFeatures();
    const scroll = computeScrollFeatures();

    return {
      ts,
      window_duration_s: Math.round(elapsed),
      hour_of_day: new Date().getHours(),
      day_of_week: new Date().getDay(),
      ...keystroke,
      ...scroll,
    };
  }

  function resetWindow() {
    keyEvents = [];
    backspaceCount = 0;
    totalKeyCount = 0;
    scrollEvents = [];
    windowStart = Date.now();
  }

  // ─── Flush every 30 seconds ───────────────────────────────────────────────

  setInterval(() => {
    const vector = buildFeatureVector();

    // Only send if there's meaningful signal (user was active)
    const hasSignal = vector.key_count > 0 || vector.scroll_event_count > 0;
    if (!hasSignal) {
      resetWindow();
      return;
    }

    // Send to background for batching + API delivery
    chrome.runtime.sendMessage({ type: "FEATURE_VECTOR", payload: vector });
    resetWindow();
  }, WINDOW_MS);

})();
