export interface KPIComponent {
  type: "kpi";
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: string;
  color?: "blue" | "green" | "orange" | "red" | "purple" | "teal";
  span?: number;
}

export interface ChartDataPoint {
  label: string;
  value: number;
  color?: string;
}

export interface DonutComponent {
  type: "donut";
  title: string;
  data: ChartDataPoint[];
  centerLabel?: string;
  centerValue?: string;
  span?: number;
}

export interface BarComponent {
  type: "bar";
  title: string;
  data: ChartDataPoint[];
  horizontal?: boolean;
  span?: number;
}

export interface LineComponent {
  type: "line";
  title: string;
  data: { label: string; value: number }[];
  xLabel?: string;
  yLabel?: string;
  span?: number;
}

export interface PieComponent {
  type: "pie";
  title: string;
  data: ChartDataPoint[];
  span?: number;
}

export interface AreaSeries {
  name: string;
  color?: string;
  data: { label: string; value: number }[];
}

export interface AreaComponent {
  type: "area";
  title: string;
  series: AreaSeries[];
  xLabel?: string;
  yLabel?: string;
  stacked?: boolean;
  span?: number;
}

export interface RadarDataPoint {
  label: string;
  value: number;
}

export interface RadarSeries {
  name: string;
  color?: string;
  data: RadarDataPoint[];
}

export interface RadarComponent {
  type: "radar";
  title: string;
  series: RadarSeries[];
  max?: number;
  span?: number;
}

export interface ScatterDataPoint {
  x: number;
  y: number;
  label?: string;
}

export interface ScatterSeries {
  name: string;
  color?: string;
  data: ScatterDataPoint[];
}

export interface ScatterComponent {
  type: "scatter";
  title: string;
  series: ScatterSeries[];
  xLabel?: string;
  yLabel?: string;
  span?: number;
}

export interface TableColumn {
  key: string;
  label: string;
  align?: "right" | "left" | "center";
}

export interface TableComponent {
  type: "table";
  title: string;
  columns: TableColumn[];
  rows: Record<string, string | number | null>[];
  span?: number;
}

export interface ProgressItem {
  label: string;
  value: number;
  max?: number;
  color?: "blue" | "green" | "orange" | "red";
}

export interface ProgressComponent {
  type: "progress";
  title: string;
  items: ProgressItem[];
  span?: number;
}

export interface StatusItem {
  label: string;
  value: string | number;
  status: "good" | "warning" | "bad" | "neutral";
}

export interface StatusGridComponent {
  type: "status-grid";
  title: string;
  items: StatusItem[];
  columns?: number;
  span?: number;
}

export type DashboardComponent =
  | KPIComponent
  | DonutComponent
  | BarComponent
  | LineComponent
  | PieComponent
  | AreaComponent
  | RadarComponent
  | ScatterComponent
  | TableComponent
  | ProgressComponent
  | StatusGridComponent;

export interface DashboardLayout {
  title: string;
  subtitle?: string;
  columns: number;
  components: DashboardComponent[];
}

export interface DashboardMessage {
  action: "render" | "clear" | "status" | "init" | "add";
  layout?: DashboardLayout;
  component?: DashboardComponent;
  status?: "idle" | "thinking" | "speaking" | "error";
  text?: string;
}
