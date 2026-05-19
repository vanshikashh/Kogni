"use client";
import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { DailyScore } from "@/types/kogni";

interface Props { scores: DailyScore[]; }

function barColor(score: number | null, isToday: boolean): string {
  if (isToday) return "#FFE600";
  if (!score) return "#333";
  if (score > 0.65) return "#E8212C";
  if (score > 0.45) return "#FF8C00";
  return "#3CB043";
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: "#0d1117",
      border: "2px solid #333",
      padding: "8px 12px",
      fontFamily: "'Press Start 2P', monospace",
      fontSize: 7,
      color: "#fff",
      lineHeight: 2,
    }}>
      <div style={{ color: "#888" }}>{d.day}</div>
      <div style={{ color: barColor(d.score, false) }}>
        SCORE: {d.score?.toFixed(2) ?? "N/A"}
      </div>
    </div>
  );
};

export function WeeklyChart({ scores }: Props) {
  const today = new Date().toDateString();

  const data = scores.map((s) => {
    const date = new Date(s.date);
    const isToday = date.toDateString() === today;
    return {
      day:     isToday ? "TODAY" : date.toLocaleDateString("en", { weekday: "short" }).toUpperCase(),
      score:   s.fatigue_score,
      isToday,
    };
  });

  // Pad to 7 days if fewer
  while (data.length < 7) {
    data.unshift({ day: "---", score: null, isToday: false });
  }

  return (
    <div
      style={{
        background: "#0d1117",
        border: "2px solid #000",
        padding: "12px 8px 8px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Grid texture overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: `
          repeating-linear-gradient(0deg, transparent, transparent 23px, rgba(0,255,65,.05) 23px, rgba(0,255,65,.05) 24px),
          repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,255,65,.05) 39px, rgba(0,255,65,.05) 40px)
        `,
      }} />

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 16, right: 8, left: -16, bottom: 4 }} barCategoryGap="28%">
          <XAxis
            dataKey="day"
            tick={{ fontFamily: "'Press Start 2P', monospace", fontSize: 5.5, fill: "#555" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tick={{ fontFamily: "'VT323', monospace", fontSize: 13, fill: "#444" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,.04)" }} />
          <ReferenceLine y={0.7} stroke="#E8212C" strokeDasharray="4 4" strokeOpacity={0.4} />
          <ReferenceLine y={0.4} stroke="#FF8C00" strokeDasharray="4 4" strokeOpacity={0.3} />
          <Bar dataKey="score" radius={[2, 2, 0, 0]} maxBarSize={36}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={barColor(entry.score, entry.isToday)}
                stroke={entry.isToday ? "#FF8C00" : "transparent"}
                strokeWidth={entry.isToday ? 1.5 : 0}
                opacity={entry.score == null ? 0.15 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
