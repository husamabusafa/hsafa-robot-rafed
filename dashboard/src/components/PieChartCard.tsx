import { useState } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { PieComponent } from "../types";

const DEFAULT_COLORS = ["#3377ff", "#8ec1ff", "#f59e0b", "#10b981", "#ef4444", "#a855f7", "#06b6d4"];

export function PieChartCard({ comp, index }: { comp: PieComponent; index: number }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const data = comp.data.map((d, i) => ({
    name: d.label,
    value: d.value,
    fill: d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
  }));
  const visibleData = data.filter((_, i) => !hidden.has(i));
  const total = visibleData.reduce((sum, d) => sum + d.value, 0);

  const toggleSlice = (i: number) => {
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
      className="glass-card p-5 flex flex-col min-h-[260px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-3 font-arabic">{comp.title}</h3>
      <div className="flex-1 flex items-center gap-3">
        <div className="flex-1 h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={visibleData}
                cx="50%"
                cy="50%"
                outerRadius="80%"
                dataKey="value"
                stroke="none"
                paddingAngle={1}
                onMouseEnter={(_, i) => setActiveIndex(i)}
                onMouseLeave={() => setActiveIndex(null)}
                animationBegin={index * 80}
                animationDuration={600}
              >
                {visibleData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.fill}
                    opacity={activeIndex === null || activeIndex === i ? 1 : 0.4}
                    style={{ transition: "opacity 0.2s", cursor: "pointer" }}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "rgba(15,23,42,0.95)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
                formatter={(value: number) => [
                  `${value.toLocaleString("en-US")} (${((value / total) * 100).toFixed(1)}%)`,
                  "",
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-2 justify-center">
        {data.map((d, i) => (
          <button
            key={i}
            onClick={() => toggleSlice(i)}
            className={`flex items-center gap-1.5 text-xs transition-opacity ${
              hidden.has(i) ? "opacity-40" : "opacity-100"
            } hover:opacity-80`}
          >
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.fill }} />
            <span className="font-arabic text-slate-400">{d.name}</span>
          </button>
        ))}
      </div>
    </motion.div>
  );
}
