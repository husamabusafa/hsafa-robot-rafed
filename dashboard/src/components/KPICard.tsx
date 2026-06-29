import { motion } from "framer-motion";
import {
  Users, Bus, UserCheck, AlertTriangle, MapPin,
  TrendingUp, Activity, Shield, Wrench, Fuel,
  type LucideIcon,
} from "lucide-react";
import type { KPIComponent } from "../types";

const ICONS: Record<string, LucideIcon> = {
  users: Users,
  bus: Bus,
  driver: UserCheck,
  accident: AlertTriangle,
  location: MapPin,
  trend: TrendingUp,
  activity: Activity,
  shield: Shield,
  wrench: Wrench,
  fuel: Fuel,
};

const COLORS: Record<string, string> = {
  blue: "from-blue-500/20 to-blue-600/5 border-blue-500/20",
  green: "from-emerald-500/20 to-emerald-600/5 border-emerald-500/20",
  orange: "from-orange-500/20 to-orange-600/5 border-orange-500/20",
  red: "from-red-500/20 to-red-600/5 border-red-500/20",
  purple: "from-purple-500/20 to-purple-600/5 border-purple-500/20",
  teal: "from-teal-500/20 to-teal-600/5 border-teal-500/20",
};

const ICON_COLORS: Record<string, string> = {
  blue: "text-blue-400",
  green: "text-emerald-400",
  orange: "text-orange-400",
  red: "text-red-400",
  purple: "text-purple-400",
  teal: "text-teal-400",
};

export function KPICard({ comp, index }: { comp: KPIComponent; index: number }) {
  const Icon = ICONS[comp.icon || "activity"] || Activity;
  const colorKey = comp.color || "blue";
  const colorClass = COLORS[colorKey] || COLORS.blue;
  const iconColor = ICON_COLORS[colorKey] || ICON_COLORS.blue;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: "easeOut" }}
      className={`glass-card bg-gradient-to-br ${colorClass} p-5 flex flex-col justify-between min-h-[140px]`}
    >
      <div className="flex items-start justify-between">
        <div className={`p-2.5 rounded-xl bg-white/5 ${iconColor}`}>
          <Icon size={24} />
        </div>
      </div>
      <div>
        <div className="text-3xl font-bold text-white tracking-tight">
          {typeof comp.value === "number" ? comp.value.toLocaleString("en-US") : comp.value}
        </div>
        <div className="text-sm text-slate-400 mt-1 font-arabic">{comp.title}</div>
        {comp.subtitle && (
          <div className="text-xs text-slate-500 mt-0.5">{comp.subtitle}</div>
        )}
      </div>
    </motion.div>
  );
}
