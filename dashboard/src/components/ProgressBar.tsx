import { motion } from "framer-motion";
import type { ProgressComponent } from "../types";

const COLORS: Record<string, string> = {
  blue: "bg-blue-500",
  green: "bg-emerald-500",
  orange: "bg-orange-500",
  red: "bg-red-500",
};

export function ProgressBarCard({ comp, index }: { comp: ProgressComponent; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[200px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-4 font-arabic">{comp.title}</h3>
      <div className="flex flex-col gap-4 flex-1 justify-center">
        {comp.items.map((item, i) => {
          const max = item.max || 100;
          const pct = Math.min((item.value / max) * 100, 100);
          const color = COLORS[item.color || "blue"] || COLORS.blue;
          return (
            <div key={i}>
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-sm text-slate-300 font-arabic">{item.label}</span>
                <span className="text-sm font-semibold text-white">
                  {item.value.toLocaleString("en-US")}
                  {item.max ? ` / ${item.max.toLocaleString("en-US")}` : "%"}
                </span>
              </div>
              <div className="h-2.5 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ delay: index * 0.08 + 0.2, duration: 0.6, ease: "easeOut" }}
                  className={`h-full rounded-full ${color}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
