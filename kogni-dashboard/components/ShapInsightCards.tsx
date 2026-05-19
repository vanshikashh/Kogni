"use client";
import { ShapDriver } from "@/types/kogni";

interface Props { drivers: ShapDriver[]; }

export function ShapInsightCards({ drivers }: Props) {
  if (!drivers.length) {
    return (
      <div style={{
        background: "#0d1117",
        border: "2px solid #222",
        padding: 12,
        fontFamily: "'VT323', monospace",
        fontSize: 16,
        color: "#555",
      }}>
        &gt; NO SHAP DATA YET — TRACKING ACTIVE...
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {drivers.map((d, i) => {
        const isGood    = d.direction === "reduces_fatigue";
        const headerBg  = isGood
          ? "linear-gradient(90deg,#1a5e1f,#3CB043)"
          : "linear-gradient(90deg,#1a3a6e,#0055CC)";
        const pct       = Math.min(100, Math.round(Math.abs(d.shap_value) * 200));
        const barColor  = isGood ? "#3CB043" : "#E8212C";

        return (
          <div key={i} style={{ border: "2px solid #000", overflow: "hidden" }}>
            {/* Header */}
            <div style={{
              background: headerBg,
              padding: "4px 10px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 5.5,
              color: "#fff",
            }}>
              <span>DRIVER #{i + 1} — {d.feature.toUpperCase()}</span>
              <span>{isGood ? "▼" : "▲"} {Math.abs(d.shap_value).toFixed(2)}</span>
            </div>

            {/* Body */}
            <div style={{ background: "#fff", padding: "8px 10px" }}>
              <div style={{
                fontFamily: "'Nunito', sans-serif",
                fontSize: 13,
                fontWeight: 700,
                color: "#111",
                marginBottom: 3,
              }}>
                {d.label}
              </div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 5,
                color: "#888",
                marginBottom: 6,
              }}>
                {isGood ? "reducing fatigue ✓" : "increasing fatigue ↑"}
              </div>

              {/* SHAP bar */}
              <div style={{
                height: 6,
                background: "#eee",
                border: "1px solid #ddd",
                overflow: "hidden",
              }}>
                <div style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: barColor,
                  transition: "width 0.6s ease",
                }} />
              </div>

              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 5,
                color: "#0055CC",
                background: "#e8f0fe",
                border: "1px solid #c5d5f8",
                padding: "2px 6px",
                marginTop: 5,
                display: "inline-block",
              }}>
                shap_value: {d.shap_value > 0 ? "+" : ""}{d.shap_value.toFixed(4)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
