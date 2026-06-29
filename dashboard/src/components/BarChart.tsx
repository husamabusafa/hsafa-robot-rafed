import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
} from "recharts";
import type { BarComponent } from "../types";

const COLORS = ["#3377ff", "#8ec1ff", "#f59e0b", "#10b981", "#ef4444", "#a855f7", "#06b6d4"];

export function BarChartCard({ comp, index }: { comp: BarComponent; index: number }) {
  const data = comp.data.map((d, i) => ({
    name: d.label,
    value: d.value,
    fill: d.color || COLORS[i % COLORS.length],
  }));

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
          <BarChart
            data={data}
            layout={comp.horizontal ? "vertical" : "horizontal"}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            {comp.horizontal ? (
              <>
                <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={80}
                />
              </>
            ) : (
              <>
                <XAxis
                  type="category"
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
              </>
            )}
            <Tooltip
              contentStyle={{
                background: "rgba(15,23,42,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
              cursor={{ fill: "rgba(255,255,255,0.05)" }}
              formatter={(value: number) => [value.toLocaleString("en-US"), ""]}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
