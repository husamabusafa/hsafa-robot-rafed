import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { DonutComponent } from "../types";

const DEFAULT_COLORS = ["#3377ff", "#8ec1ff", "#f59e0b", "#10b981", "#ef4444", "#a855f7"];

export function DonutChart({ comp, index }: { comp: DonutComponent; index: number }) {
  const data = comp.data.map((d, i) => ({
    name: d.label,
    value: d.value,
    fill: d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
  }));
  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[260px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-3 font-arabic">{comp.title}</h3>
      <div className="flex-1 relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="55%"
              outerRadius="80%"
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
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
        {(comp.centerValue || comp.centerLabel) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            {comp.centerValue && (
              <div className="text-2xl font-bold text-white">
                {comp.centerValue}
              </div>
            )}
            {comp.centerLabel && (
              <div className="text-xs text-slate-400 mt-0.5 font-arabic">{comp.centerLabel}</div>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2 mt-2 justify-center">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.fill }} />
            <span className="font-arabic">{d.name}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
