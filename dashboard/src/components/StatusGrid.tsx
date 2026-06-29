import { motion } from "framer-motion";
import { CheckCircle, AlertCircle, XCircle, MinusCircle } from "lucide-react";
import type { StatusGridComponent } from "../types";

const STATUS_CONFIG = {
  good: { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  warning: { icon: AlertCircle, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  bad: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  neutral: { icon: MinusCircle, color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/20" },
};

export function StatusGrid({ comp, index }: { comp: StatusGridComponent; index: number }) {
  const cols = comp.columns || 3;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[200px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-4 font-arabic">{comp.title}</h3>
      <div
        className="grid gap-3 flex-1"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {comp.items.map((item, i) => {
          const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.neutral;
          const Icon = cfg.icon;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.08 + i * 0.04, duration: 0.3 }}
              className={`flex items-center gap-3 p-3 rounded-xl border ${cfg.bg} ${cfg.border}`}
            >
              <Icon size={20} className={cfg.color} />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-slate-400 font-arabic truncate">{item.label}</div>
                <div className={`text-lg font-bold ${cfg.color}`}>{item.value}</div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
