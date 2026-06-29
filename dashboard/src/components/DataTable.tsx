import { motion } from "framer-motion";
import type { TableComponent } from "../types";

export function DataTable({ comp, index }: { comp: TableComponent; index: number }) {
  const maxRows = 12;
  const rows = comp.rows.slice(0, maxRows);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass-card p-5 flex flex-col min-h-[260px] overflow-hidden"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-3 font-arabic">{comp.title}</h3>
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {comp.columns.map((col) => (
                <th
                  key={col.key}
                  className={`py-2 px-3 font-semibold text-slate-400 text-xs uppercase tracking-wider font-arabic ${
                    col.align === "center" ? "text-center" : col.align === "left" ? "text-left" : "text-right"
                  }`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-white/5 hover:bg-white/5 transition-colors"
              >
                {comp.columns.map((col) => (
                  <td
                    key={col.key}
                    className={`py-2 px-3 text-slate-300 ${
                      col.align === "center" ? "text-center" : col.align === "left" ? "text-left" : "text-right"
                    }`}
                  >
                    {row[col.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {comp.rows.length > maxRows && (
          <div className="text-center text-xs text-slate-500 py-2">
            +{comp.rows.length - maxRows} صف إضافي
          </div>
        )}
      </div>
    </motion.div>
  );
}
