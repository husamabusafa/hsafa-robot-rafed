import { motion } from "framer-motion";
import {
  LineChart as ReLineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip,
} from "recharts";
import type { LineComponent } from "../types";

export function LineChartCard({ comp, index }: { comp: LineComponent; index: number }) {
  const data = comp.data.map((d) => ({ name: d.label, value: d.value }));

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
          <ReLineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
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
              formatter={(value: number) => [value.toLocaleString("en-US"), ""]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3377ff"
              strokeWidth={2.5}
              dot={{ fill: "#3377ff", r: 3 }}
              activeDot={{ r: 5 }}
            />
          </ReLineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
