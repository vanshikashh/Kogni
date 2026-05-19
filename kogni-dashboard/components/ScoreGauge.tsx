"use client";
import { FatigueStatus } from "@/types/kogni";

interface Props {
  score: number | null;
  status?: FatigueStatus;
  animated?: boolean;
}

const STATUS_COLOR: Record<FatigueStatus, string> = {
  nominal:  "#00FF41",
  moderate: "#FF8C00",
  high:     "#E8212C",
};

const STATUS_LABEL: Record<FatigueStatus, string> = {
  nominal:  "NOMINAL",
  moderate: "MODERATE",
  high:     "HIGH FATIGUE",
};

export function ScoreGauge({ score, status = "nominal", animated = false }: Props) {
  const color = STATUS_COLOR[status];
  const label = STATUS_LABEL[status];
  const pct   = score != null ? Math.round(score * 100) : null;

  return (
    <div className="flex flex-col items-start gap-1">
      {/* Big number */}
      <div
        className="font-vt text-[88px] leading-none tabular-nums"
        style={{
          color,
          textShadow: `0 0 24px ${color}55`,
          fontFamily: "'VT323', monospace",
          transition: animated ? "color 0.6s ease" : undefined,
        }}
      >
        {score != null ? score.toFixed(2) : "-.--"}
        <span style={{ fontSize: 32, opacity: 0.5 }}>/1.0</span>
      </div>

      {/* Status bar */}
      <div className="w-full h-3 bg-black border-2 border-black overflow-hidden">
        <div
          className="h-full transition-all duration-700"
          style={{
            width: pct != null ? `${pct}%` : "0%",
            background: `linear-gradient(90deg, ${color}99, ${color})`,
            backgroundSize: "8px 100%",
            backgroundImage: `repeating-linear-gradient(90deg, transparent, transparent 6px, rgba(255,255,255,.15) 6px, rgba(255,255,255,.15) 8px), linear-gradient(90deg, ${color}88, ${color})`,
          }}
        />
      </div>

      {/* Status label */}
      <div className="flex items-center gap-2 mt-1">
        <span
          className="w-2 h-2 rounded-full"
          style={{
            background: color,
            boxShadow: `0 0 6px ${color}`,
            animation: animated ? "pulse 1.5s ease-in-out infinite" : undefined,
          }}
        />
        <span
          className="text-[7px] font-pixel tracking-widest"
          style={{ color, fontFamily: "'Press Start 2P', monospace" }}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
