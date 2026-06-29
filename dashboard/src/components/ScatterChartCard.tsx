import { useState } from "react";
import { motion } from "framer-motion";
import {
  ScatterChart as ReScatterChart, Scatter, XAxis, YAxis, ZAxis,
  ResponsiveContainer, Tooltip, CartesianGrid,
} from "recharts";
import type { ScatterComponent } from "../types";

const DEFAULT_COLORS = ["#3377ff", "#10b981", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4"];

export function ScatterChartCard({ comp, index }: { comp: ScatterComponent; index: number }) {
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const colors = comp.series.map((s, i) => s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]);
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
          <ReScatterChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              type="number"
              dataKey="x"
              name={comp.xLabel || "x"}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              label={comp.xLabel ? { value: comp.xLabel, position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 11 } : undefined}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={comp.yLabel || "y"}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              label={comp.yLabel ? { value: comp.yLabel, angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 11 } : undefined}
            />
            <ZAxis range={[60, 60]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: "rgba(255,255,255,0.15)" }}
              contentStyle={{
                background: "rgba(15,23,42,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
              formatter={(value: number, name: string) => [value.toLocaleString("en-US"), name]}
            />
            {visibleSeries.map((s) => (
              <Scatter
                key={s.idx}
                name={s.name}
                data={s.data}
                fill={colors[s.idx]}
                fillOpacity={0.7}
                animationBegin={index * 80}
                animationDuration={600}
              />
            ))}
          </ReScatterChart>
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
