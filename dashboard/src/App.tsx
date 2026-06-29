import { AnimatePresence, motion } from "framer-motion";
import { Bot, Wifi, WifiOff } from "lucide-react";
import { useWebSocket } from "./hooks/useWebSocket";
import { ComponentRenderer } from "./components/ComponentRenderer";

export default function App() {
  const { layout, status, connected } = useWebSocket();

  return (
    <div className="w-screen h-screen flex flex-col bg-[#0a0e1a] overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
            <Bot size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Haseef Command Center</h1>
            <p className="text-xs text-slate-500 font-arabic">مركز قيادة حصيف</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {status === "thinking" && (
            <div className="flex items-center gap-2 text-sm text-brand-400">
              <div className="thinking-dots">
                <span />
                <span />
                <span />
              </div>
              <span className="font-arabic">حصيف يفكر...</span>
            </div>
          )}
          {status === "speaking" && (
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-arabic">يتحدث</span>
            </div>
          )}
          <div className={`flex items-center gap-1.5 text-xs ${connected ? "text-emerald-400" : "text-red-400"}`}>
            {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            <span>{connected ? "متصل" : "غير متصل"}</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        <AnimatePresence mode="wait">
          {layout ? (
            <motion.div
              key={layout.title}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {/* Dashboard title */}
              <div className="mb-5">
                <h2 className="text-2xl font-bold gradient-text font-arabic">{layout.title}</h2>
                {layout.subtitle && (
                  <p className="text-sm text-slate-400 mt-1 font-arabic">{layout.subtitle}</p>
                )}
              </div>

              {/* Components grid */}
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: `repeat(${layout.columns}, minmax(0, 1fr))`,
                }}
              >
                {layout.components.map((comp, i) => {
                  const span = "span" in comp ? comp.span || 1 : 1;
                  return (
                    <div
                      key={i}
                      style={{
                        gridColumn: span > 1 ? `span ${span}` : undefined,
                      }}
                    >
                      <ComponentRenderer comp={comp} index={i} />
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-full gap-6"
            >
              <motion.div
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                className="w-24 h-24 rounded-3xl bg-gradient-to-br from-brand-500/20 to-brand-700/10 border border-brand-500/20 flex items-center justify-center"
              >
                <Bot size={48} className="text-brand-400" />
              </motion.div>
              <div className="text-center">
                <p className="text-xl text-slate-300 font-arabic">في انتظار أسئلتك...</p>
                <p className="text-sm text-slate-500 mt-1">Ask Haseef about school transport data</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
