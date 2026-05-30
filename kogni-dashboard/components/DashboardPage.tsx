"use client";
import { useEffect, useState, useCallback } from "react";
import { fetchWeeklyReport } from "@/lib/api";
import { useLiveScore } from "@/hooks/useLiveScore";
import { WeeklyReport, ShapDriver } from "@/types/kogni";
import { ScoreGauge } from "@/components/ScoreGauge";
import { WeeklyChart } from "@/components/WeeklyChart";
import { ShapInsightCards } from "@/components/ShapInsightCards";
import { RecoveryModal } from "@/components/RecoveryModal";

const WIN_STYLE: React.CSSProperties = {
  background: "#fff",
  border: "3px solid #000",
  boxShadow: "4px 4px 0 #000",
};

const TITLE_STYLE: React.CSSProperties = {
  background: "linear-gradient(180deg,#1a6fe8 0%,#0055CC 100%)",
  padding: "4px 8px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  borderBottom: "2px solid #000",
};

const PANEL_TITLE: React.CSSProperties = {
  fontFamily: "'Press Start 2P', monospace",
  fontSize: 6,
  color: "#0055CC",
  marginBottom: 10,
  paddingBottom: 7,
  borderBottom: "2px dashed rgba(0,0,0,.12)",
  display: "flex",
  alignItems: "center",
  gap: 5,
};

function WinTitle({ icon, title }: { icon: string; title: string }) {
  return (
    <div style={TITLE_STYLE}>
      <div style={{
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 6.5, color: "#fff",
        textShadow: "1px 1px 0 rgba(0,0,0,.4)",
        display: "flex", alignItems: "center", gap: 6,
      }}>
        <span style={{ fontSize: 14 }}>{icon}</span>
        {title}
      </div>
      <div style={{ display: "flex", gap: 2 }}>
        {["#FFE600", "#3CB043", "#E8212C"].map((c, i) => (
          <div key={i} style={{
            width: 14, height: 14,
            background: c,
            border: "2px solid #000",
          }} />
        ))}
      </div>
    </div>
  );
}

function Badge({ children, color = "#0055CC", bg = "#e8f0fe" }: {
  children: React.ReactNode; color?: string; bg?: string;
}) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontFamily: "'Press Start 2P', monospace", fontSize: 5.5,
      border: "2px solid #000", padding: "3px 7px",
      background: bg, color,
    }}>{children}</span>
  );
}

export function DashboardPage({ onLogout }: { onLogout: () => void }) {
  const { liveScore, intervention, connected, dismissIntervention } = useLiveScore();
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [vecCount, setVecCount] = useState(847);
  const [time, setTime] = useState("");

  const loadReport = useCallback(async () => {
    try {
      const data = await fetchWeeklyReport();
      setReport(data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadReport();
    // Refresh every 5 minutes
    const t = setInterval(loadReport, 2 * 60 * 1000);
    return () => clearInterval(t);
  }, [loadReport]);

  // Clock
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setTime(`${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`);
    };
    tick();
    const t = setInterval(tick, 10000);
    return () => clearInterval(t);
  }, []);

  // Simulate vector count growing
  useEffect(() => {
    const t = setInterval(() => setVecCount(v => v + 1), 3000);
    return () => clearInterval(t);
  }, []);

  // Use latest score from weekly report as fallback when WebSocket unavailable
  const latestScore = report?.scores?.filter(s => s.fatigue_score != null).slice(-1)[0];
  const score  = liveScore?.fatigue_score ?? latestScore?.fatigue_score ?? null;
  const status = (liveScore?.status ?? (score && score > 0.7 ? "high" : score && score > 0.4 ? "moderate" : "nominal")) as FatigueStatus;
  // Pull SHAP from weekly report latest score (works without WebSocket)
  const shapSource = latestScore ?? report?.scores?.slice(-1)[0];
  const shap: ShapDriver[] = liveScore?.shap_top3 ?? (
    shapSource?.shap_feature_1 ? [
      { feature: shapSource.shap_feature_1 ?? "", label: shapSource.shap_feature_1?.replace("_"," ") ?? "", shap_value: shapSource.shap_value_1 ?? 0, direction: (shapSource.shap_value_1 ?? 0) > 0 ? "increases_fatigue" : "reduces_fatigue" },
      ...(shapSource.shap_feature_2 ? [{ feature: shapSource.shap_feature_2, label: shapSource.shap_feature_2.replace("_"," "), shap_value: shapSource.shap_value_2 ?? 0, direction: ((shapSource.shap_value_2 ?? 0) > 0 ? "increases_fatigue" : "reduces_fatigue") as "increases_fatigue" | "reduces_fatigue" }] : []),
      ...(shapSource.shap_feature_3 ? [{ feature: shapSource.shap_feature_3, label: shapSource.shap_feature_3.replace("_"," "), shap_value: shapSource.shap_value_3 ?? 0, direction: ((shapSource.shap_value_3 ?? 0) > 0 ? "increases_fatigue" : "reduces_fatigue") as "increases_fatigue" | "reduces_fatigue" }] : []),
    ] : []
  );
  const scores = report?.scores ?? [];

  const MetricCard = ({ icon, label, value, unit, delta, deltaDir }: {
    icon: string; label: string; value: string; unit: string;
    delta: string; deltaDir: "up" | "dn";
  }) => (
    <div style={{ padding: 14, borderRight: "2px solid #000" }}>
      <div style={PANEL_TITLE}>{icon} {label}</div>
      <div style={{
        fontFamily: "'VT323', monospace",
        fontSize: 46, lineHeight: 1, color: "#0055CC",
        margin: "4px 0 2px",
      }}>
        {value}<span style={{ fontSize: 20, opacity: .6 }}>{unit}</span>
      </div>
      <div style={{
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 5.5, color: "#888",
      }}>{label}</div>
      <div style={{
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 5, marginTop: 5,
        color: deltaDir === "up" ? "#E8212C" : "#3CB043",
        display: "flex", alignItems: "center", gap: 3,
      }}>
        {deltaDir === "up" ? "▲" : "▼"} {delta}
      </div>
    </div>
  );

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg,#87CEEB 0%,#b8e4f9 44%,#a8d8a8 44%,#5aad50 100%)",
      paddingBottom: 44,
    }}>
      {/* Taskbar */}
      <div style={{
        position: "fixed", bottom: 0, left: 0, right: 0, height: 34,
        background: "linear-gradient(180deg,#245EDC,#1440A8)",
        borderTop: "2px solid #0033AA",
        display: "flex", alignItems: "center", gap: 4,
        padding: "2px 6px", zIndex: 1000,
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 5,
          background: "linear-gradient(180deg,#3d8c2c,#2a6a1c)",
          border: "2px solid #000", borderRadius: 10,
          padding: "3px 12px 3px 8px",
          fontFamily: "'Press Start 2P', monospace", fontSize: 7, color: "#fff",
          cursor: "pointer", height: 26,
        }}>🟢 <strong>START</strong></div>

        <div style={{ width: 2, height: 22, background: "rgba(255,255,255,.2)", margin: "0 3px" }} />

        <div style={{
          background: "rgba(0,0,0,.25)", border: "1px solid rgba(255,255,255,.4)",
          padding: "2px 10px", height: 24, display: "flex", alignItems: "center", gap: 4,
          fontFamily: "'Press Start 2P', monospace", fontSize: 5, color: "#fff",
        }}>🧠 KOGNI.EXE</div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: connected ? "#00FF41" : "#666",
            boxShadow: connected ? "0 0 6px #00FF41" : "none",
          }} />
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 6.5, color: "#fff",
            background: "rgba(0,0,0,.2)", padding: "3px 8px",
            border: "1px solid rgba(255,255,255,.2)",
          }}>{time}</div>
        </div>
      </div>

      {/* Main content */}
      <div style={{ padding: "16px 16px 0 16px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={WIN_STYLE}>
          <WinTitle icon="🧠" title="KOGNI v0.1.0 — Cognitive Health Monitor" />

          {/* Ticker */}
          <div style={{
            display: "flex", alignItems: "center", overflow: "hidden",
            height: 24, background: "#0055CC",
            borderBottom: "2px solid #000",
          }}>
            <div style={{
              background: "#E8212C", fontFamily: "'Press Start 2P', monospace",
              fontSize: 5, color: "#fff", padding: "0 8px", height: "100%",
              display: "flex", alignItems: "center", borderRight: "2px solid #000",
              flexShrink: 0,
            }}>LIVE</div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <div style={{
                display: "flex", gap: "2rem",
                animation: "tkm 22s linear infinite",
                whiteSpace: "nowrap", padding: "0 1rem",
              }}>
                {[
                  `FATIGUE: ${score?.toFixed(2) ?? "--"} — ${status.toUpperCase()}`,
                  `VECTORS TODAY: ${vecCount}`,
                  `TREND: ${report?.trend_direction?.toUpperCase() ?? "LOADING..."}`,
                  `AVG FATIGUE: ${report?.avg_fatigue?.toFixed(2) ?? "--"}`,
                  `EXTENSION: ${connected ? "ACTIVE" : "DISCONNECTED"}`,
                  `FATIGUE: ${score?.toFixed(2) ?? "--"} — ${status.toUpperCase()}`,
                  `VECTORS TODAY: ${vecCount}`,
                ].map((t, i) => (
                  <span key={i} style={{
                    fontFamily: "'Press Start 2P', monospace", fontSize: 5,
                    color: "rgba(255,255,255,.85)", display: "inline-flex",
                    alignItems: "center", gap: 6,
                  }}>
                    <span style={{ width: 4, height: 4, background: "#FFE600", display: "inline-block" }} />
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Row 1 — Score + 3 metrics */}
          <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 1fr 1fr", borderTop: "2px solid #000" }}>
            {/* Score */}
            <div style={{ padding: 14, borderRight: "2px solid #000" }}>
              <div style={PANEL_TITLE}>⬛ FATIGUE INDEX</div>
              <ScoreGauge score={score} status={status} animated />
              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 3 }}>
                <Badge bg={connected ? "#e1f5ee" : "#f1efe8"} color={connected ? "#085041" : "#666"}>
                  <span style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: connected ? "#00FF41" : "#999",
                    boxShadow: connected ? "0 0 4px #00FF41" : "none",
                    display: "inline-block",
                  }} />
                  {connected ? "LIVE" : "OFFLINE"}
                </Badge>
                <Badge bg="#e8f0fe" color="#0055CC">RF v0.1</Badge>
                <Badge bg="#e1f5ee" color="#085041">SHAP ✓</Badge>
              </div>
            </div>

            <MetricCard
              icon="⌨" label="IKI MEAN"
              value="186" unit="ms"
              delta="12ms below baseline" deltaDir="dn"
            />
            <MetricCard
              icon="↕" label="SCROLL VEL"
              value="847" unit="px/s"
              delta="203px/s above baseline" deltaDir="up"
            />
            <div style={{ padding: 14 }}>
              <div style={PANEL_TITLE}>📦 VECTORS</div>
              <div style={{
                fontFamily: "'VT323', monospace",
                fontSize: 46, lineHeight: 1, color: "#3CB043",
                margin: "4px 0 2px",
              }}>{vecCount}</div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 5.5, color: "#888",
              }}>EVENTS TODAY</div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 5, marginTop: 5, color: "#3CB043",
              }}>● STREAMING LIVE</div>
            </div>
          </div>

          {/* Row 2 — Chart + SHAP */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", borderTop: "2px solid #000" }}>
            {/* Chart */}
            <div style={{ padding: 14, borderRight: "2px solid #000" }}>
              <div style={PANEL_TITLE}>📈 7-DAY COGNITIVE FINGERPRINT</div>
              {loading ? (
                <div style={{
                  background: "#0d1117", height: 180,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "'VT323', monospace", fontSize: 20, color: "#3CB043",
                  border: "2px solid #000",
                }}>LOADING DATA...</div>
              ) : (
                <WeeklyChart scores={scores} />
              )}
              <div style={{ display: "flex", gap: 4, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
                {report && (
                  <>
                    <Badge
                      bg={report.trend_direction === "improving" ? "#e1f5ee" : report.trend_direction === "declining" ? "#fdecea" : "#f1efe8"}
                      color={report.trend_direction === "improving" ? "#085041" : report.trend_direction === "declining" ? "#7a1313" : "#444"}
                    >
                      {report.trend_direction === "improving" ? "▼" : report.trend_direction === "declining" ? "▲" : "→"} {report.trend_direction.toUpperCase()}
                    </Badge>
                    {report.avg_fatigue != null && (
                      <Badge bg="#e8f0fe" color="#0055CC">AVG: {report.avg_fatigue.toFixed(2)}</Badge>
                    )}
                  </>
                )}
                <span style={{
                  fontFamily: "'Press Start 2P', monospace", fontSize: 5, color: "#888", marginLeft: "auto",
                }}>■ TODAY &nbsp; ■ NORMAL &nbsp; ■ HIGH</span>
              </div>
            </div>

            {/* SHAP */}
            <div style={{ padding: 14 }}>
              <div style={PANEL_TITLE}>💡 SHAP DRIVERS</div>
              <ShapInsightCards drivers={shap} />
            </div>
          </div>

          {/* Status strip */}
          <div style={{
            background: "#f0f0f0",
            borderTop: "2px solid #000",
            display: "flex", gap: 2, padding: "3px 6px",
          }}>
            {[
              { dot: connected, label: "API" },
              { dot: connected, label: "EXT" },
              { dot: false, label: "LSTM: PHASE 4" },
            ].map((s, i) => (
              <div key={i} style={{
                fontFamily: "'Press Start 2P', monospace", fontSize: 5.5,
                padding: "2px 8px", border: "2px solid #c0c0c0",
                borderColor: "#808080 #fff #fff #808080",
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span style={{
                  width: 6, height: 6,
                  background: s.dot ? "#00FF41" : "#999",
                  boxShadow: s.dot ? "0 0 4px #00FF41" : "none",
                  borderRadius: "50%", border: "1px solid rgba(0,0,0,.2)",
                  display: "inline-block",
                }} />
                {s.label}
              </div>
            ))}
            <div style={{ marginLeft: "auto", fontFamily: "'Press Start 2P', monospace", fontSize: 5.5, color: "#888", padding: "2px 6px" }}>
              VECTORS: {vecCount}
            </div>
            <button
              onClick={onLogout}
              style={{
                fontFamily: "'Press Start 2P', monospace", fontSize: 5.5,
                border: "none", background: "none", cursor: "pointer", color: "#E8212C",
              }}
            >LOGOUT</button>
          </div>
        </div>
      </div>

      {/* Recovery modal */}
      {intervention && (
        <RecoveryModal intervention={intervention} onDismiss={dismissIntervention} />
      )}

      <style>{`
        @keyframes tkm { from { transform: translateX(0) } to { transform: translateX(-50%) } }
      `}</style>
    </div>
  );
}
