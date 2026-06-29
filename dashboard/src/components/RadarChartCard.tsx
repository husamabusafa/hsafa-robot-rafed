import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  RadarChart as ReRadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import type { RadarComponent } from "../types";

const DEFAULT_COLORS = ["#3377ff", "#10b981", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4"];

export function RadarChartCard({ comp, index }: { comp: RadarComponent; index: number }) {
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const colors = comp.series.map((s, i) => s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]);

  const data = useMemo(() => {
    const labels = new Set<string>();
    comp.series.forEach((s) => s.data.forEach((d) => labels.add(d.label)));
    return Array.from(labels).map((label) => {
      const row: Record<string, string | number> = { label };
      comp.series.forEach((s, i) => {
        const point = s.data.find((d) => d.label === label);
        row[`s${i}`] = point ? point.value : 0;
      });
      return row;
    });
  }, [comp.series]);

  const visibleSeries = comp.series.map((s, i) => ({ ...s, idx: i })).filter((s) => !hidden.has(s.idx));
  const maxVal = comp.max || Math.max(...comp.series.flatMap((s) => s.data.map((d) => d.value)), 100);

  const toggleSeries = (i: number) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[300px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-3 font-arabic">{comp.title}</h3>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ReRadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="rgba(255,255,255,0.08)" />
            <PolarAngleAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <PolarRadiusAxis
              angle={90}
              domain={[0, maxVal]}
              tick={{ fill: "#475569", fontSize: 9 }}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "rgba(15,23,42,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
              formatter={(value: number, name: string) => {
                const s = comp.series[Number(name.slice(1))];
                return [value.toLocaleString("en-US"), s?.name || ""];
              }}
            />
            {visibleSeries.map((s) => (
              <Radar
                key={s.idx}
                name={`s${s.idx}`}
                dataKey={`s${s.idx}`}
                stroke={colors[s.idx]}
                fill={colors[s.idx]}
                fillOpacity={0.15}
                strokeWidth={2}
                animationBegin={index * 80}
                animationDuration={600}
              />
            ))}
          </ReRadarChart>
        </ResponsiveContainer>
      </div>
      {comp.series.length > 1 && (
        <div className="flex flex-wrap gap-3 mt-2 justify-center">
          {comp.series.map((s, i) => (
            <button
              key={i}
              onClick={() => toggleSeries(i)}
              className={`flex items-center gap-1.5 text-xs transition-opacity ${
                hidden.has(i) ? "opacity-40" : "opacity-100"
              } hover:opacity-80`}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: colors[i] }} />
              <span className="font-arabic text-slate-400">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
