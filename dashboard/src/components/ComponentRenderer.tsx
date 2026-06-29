import type { DashboardComponent } from "../types";
import { KPICard } from "./KPICard";
import { DonutChart } from "./DonutChart";
import { BarChartCard } from "./BarChart";
import { LineChartCard } from "./LineChart";
import { PieChartCard } from "./PieChartCard";
import { AreaChartCard } from "./AreaChartCard";
import { RadarChartCard } from "./RadarChartCard";
import { ScatterChartCard } from "./ScatterChartCard";
import { DataTable } from "./DataTable";
import { ProgressBarCard } from "./ProgressBar";
import { StatusGrid } from "./StatusGrid";

export function ComponentRenderer({ comp, index }: { comp: DashboardComponent; index: number }) {
  switch (comp.type) {
    case "kpi":
      return <KPICard comp={comp} index={index} />;
    case "donut":
      return <DonutChart comp={comp} index={index} />;
    case "bar":
      return <BarChartCard comp={comp} index={index} />;
    case "line":
      return <LineChartCard comp={comp} index={index} />;
    case "pie":
      return <PieChartCard comp={comp} index={index} />;
    case "area":
      return <AreaChartCard comp={comp} index={index} />;
    case "radar":
      return <RadarChartCard comp={comp} index={index} />;
    case "scatter":
      return <ScatterChartCard comp={comp} index={index} />;
    case "table":
      return <DataTable comp={comp} index={index} />;
    case "progress":
      return <ProgressBarCard comp={comp} index={index} />;
    case "status-grid":
      return <StatusGrid comp={comp} index={index} />;
    default:
      return null;
  }
}
