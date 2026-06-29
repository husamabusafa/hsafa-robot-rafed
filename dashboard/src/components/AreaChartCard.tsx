import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  AreaChart as ReAreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid,
} from "recharts";
import type { AreaComponent } from "../types";

const DEFAULT_COLORS = ["#3377ff", "#10b981", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4"];

export function AreaChartCard({ comp, index }: { comp: AreaComponent; index: number }) {
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const colors = comp.series.map((s, i) => s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]);

  const data = useMemo(() => {
    const labels = new Set<string>();
    comp.series.forEach((s) => s.data.forEach((d) => labels.add(d.label)));
    return Array.from(labels).map((label) => {
      const row: Record<string, string | number> = { name: label };
      comp.series.forEach((s, i) => {
        const point = s.data.find((d) => d.label === label);
        row[`s${i}`] = point ? point.value : 0;
      });
      return row;
    });
  }, [comp.series]);

  const visibleSeries = comp.series.map((s, i) => ({ ...s, idx: i })).filter((s) => !hidden.has(s.idx));

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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[260px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-3 font-arabic">{comp.title}</h3>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ReAreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
            <defs>
              {colors.map((c, i) => (
                <linearGradient key={i} id={`area-grad-${index}-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={c} stopOpacity={0.02} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: "#64748b", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              interval={0}
              angle={-15}
              textAnchor="end"
              height={50}
            />
            <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
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
              <Area
                key={s.idx}
                type="monotone"
                dataKey={`s${s.idx}`}
                stroke={colors[s.idx]}
                strokeWidth={2.5}
                fill={`url(#area-grad-${index}-${s.idx})`}
                stackId={comp.stacked ? "1" : undefined}
                animationBegin={index * 80}
                animationDuration={600}
              />
            ))}
          </ReAreaChart>
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
              <span className="w-3 h-1 rounded-full" style={{ background: colors[i] }} />
              <span className="font-arabic text-slate-400">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
