const badge = document.getElementById("status-badge");
const scoreSection = document.getElementById("score-section");
const scoreVal = document.getElementById("score-val");
const scoreLabel = document.getElementById("score-label");

chrome.storage.local.get("kogni_token", (result) => {
  if (result.kogni_token) {
    badge.textContent = "Tracking active";
    badge.className = "badge active";
    scoreSection.style.display = "block";
  }
});

chrome.runtime.sendMessage({ type: "GET_BADGE_STATE" }, (response) => {
  if (!response || response.score === null) return;
  const s = response.score;
  scoreVal.textContent = s.toFixed(2);
  if (s < 0.4)      scoreLabel.textContent = "Good";
  else if (s < 0.7) scoreLabel.textContent = "Moderate fatigue";
  else               scoreLabel.textContent = "High fatigue";
});
