# Rafed × Haseef — Data Intelligence & Interactive Dashboard Plan

## Overview

Haseef becomes a full data intelligence agent for the Rafed school transport data warehouse. It can:

1. **Answer any question** from the 13.5M row database (16 query tools)
2. **Control an interactive React dashboard** — render charts, maps, grids, KPI cards, tables, and any visualization it decides is best for the question
3. **React in real-time** — update the dashboard as conversations evolve

Gemini (voice) only calls `queue_thinker_task`. Haseef does ALL the work: queries data, decides the best visualization, sends render instructions to the frontend.

---

## Architecture

```
User speaks (Arabic/English)
    ↓
Gemini Live — understands intent, calls queue_thinker_task
    ↓
Haseef (thinker) receives task
    ↓
┌─────────────────────────────────────────┐
│  Haseef Brain                           │
│                                         │
│  1. Understand question                 │
│  2. Pick right tool(s)                  │
│  3. Query PostgreSQL (asyncpg)          │
│  4. Analyze results                     │
│  5. Decide best visualization           │
│  6. Send UI render spec to frontend     │
│  7. Send text answer back to Gemini     │
└─────────────────────────────────────────┘
    ↓                    ↓
Gemini speaks answer    React Dashboard renders
                         (WebSocket / SSE)
```

### Data Flow

```
┌──────────┐     ┌───────────┐     ┌──────────────┐     ┌────────────┐
│  Gemini  │────▶│  Haseef   │────▶│  PostgreSQL  │     │  React     │
│  (voice) │     │  (brain)  │     │  (Rafed DB)  │     │  Dashboard │
└──────────┘     └───────────┘     └──────────────┘     └────────────┘
                        │                                        ▲
                        │  1. Query data                         │
                        │  2. Get results                        │
                        │  3. Build render spec (JSON)            │
                        └────────────────────────────────────────┘
                              WebSocket / SSE push
```

---

## Database Schema (v_current — latest)

### Dimension Tables

| Table | Rows | Description (AR) |
|-------|------|-------------------|
| `dim_school` | 11,740 | المدارس — الاسم، الموقع، القطاع، الإدارة، المقاعد |
| `dim_noor_school` | 11,738 | مدارس نور — ربط مع نظام نور |
| `dim_vehicle` | 25,512 | الحافلات — اللوحة، GPS، السعة، التأمين، الرخصة |
| `dim_driver` | 28,127 | السائقين — الاسم، الجنسية، الرخصة، التدريب، الامتثال |
| `dim_escort` | 9,038 | المرافقين على الحافلة |
| `dim_operator` | 4,544 | مشغلي النقل / المقاولين |
| `dim_contract` | 160 | العقود — المشغل، المقاعد، المبالغ، التواريخ |
| `dim_inspector` | 263 | المفتشين الميدانيين |
| `dim_geofence` | — | المناطق الجغرافية للمدارس |
| `dim_domain` | 7,668 | قيم المرجع (عربي + إنجليزي) |
| `dim_calendar` | 729 | التقويم المدرسي مع التواريخ الهجرية والعطل |
| `dim_weather_daily` | 8 | بيانات الطقس اليومية |

### Fact Tables

| Table | Rows | Description (AR) |
|-------|------|-------------------|
| `fact_school_visit` | 5,878,550 | زيارات الحافلات للمدارس (وصول/مغادرة، GPS، وقت) |
| `fact_inspection_answer` | 4,369,881 | إجابات أسئلة التفتيش الفردية |
| `fact_ins_violence` | 2,012,310 | حوادث العنف في الحافلات |
| `fact_assignment` | 748,909 | تعيين الطلاب للحافلات (GPS المنزل، المسافة) |
| `fact_inspection_detail` | 156,101 | ملخصات زيارات التفتيش |
| `ins_workorders` | 61,341 | أوامر عمل التفتيش |
| `fact_survey_answer` | 53,882 | إجابات الاستبيانات |
| `fact_safety_check` | 45,847 | فحوصات الأمان اليومية (12+ سؤال) |
| `fact_vehicle_kpi` | 25,512 | مؤشرات أداء الحافلات (استخدام، مخالفات، عمر) |
| `fact_plan_route` | 21,893 | المسارات المخططة لكل مدرسة/حافلة |
| `fact_driver_training` | 18,576 | سجلات تدريب السائقين |
| `fact_batch_import` | 17,992 | تتبع استيراد الدفعات |
| `fact_seat_gap` | 11,738 | فجوات المقاعد (المخصص vs الفعلي) |
| `fact_ins_accident` | 561 | تقارير الحوادث (إصابات، وفيات) |
| `fact_safety_accident` | 201 | حوادث مبلغ عنها عبر التطبيق |
| `fact_audit_violation` | 441 | مخالفات التدقيق |
| `fact_complaint` | 621 | الشكاوى |
| `fact_contract_readiness` | 80 | مؤشرات جاهزية العقد |
| `fact_daily_snapshot` | 1 | لقطة يومية مجمعة |
| `fact_fuel` | — | بيانات الوقود |
| `fact_geofence_event` | — | أحداث المناطق الجغرافية |
| `fact_ridership_daily` | — | الركوب اليومي |
| `fact_trip_daily` | — | الرحلات اليومية |

### Materialized Views

| Table | Rows | Description |
|-------|------|-------------|
| `mv_plan_summary` | 80 | ملخص التخطيط (عقد، مشغل، حافلات، طلاب) |
| `mv_school_plan` | 11,425 | خطة المدرسة (حافلات، طلاب مخطط) |
| `mv_school_seat_gap` | 11,738 | فجوة مقاعد المدرسة (مخصص، فعلي، نسبة) |

### Key Relationships

```
dim_contract ──◀ fact_assignment ──▶ dim_school
     │                │                   │
     │                ├────▶ dim_vehicle  │
     │                ├────▶ dim_driver   │
     │                │                   │
     ├────▶ fact_ins_accident             │
     ├────▶ fact_inspection_detail        │
     ├────▶ fact_complaint                │
     ├────▶ fact_seat_gap ──▶ dim_school  │
     ├────▶ fact_plan_route               │
     ├────▶ fact_vehicle_kpi ─▶ dim_vehicle
     ├────▶ fact_contract_readiness       │
     │                                     │
dim_operator ──▶ dim_vehicle              │
dim_inspector ──▶ ins_workorders ─▶ dim_school
dim_geofence ──▶ fact_geofence_event ─▶ dim_vehicle
dim_calendar ──▶ (all fact tables via date columns)
```

---

## Part 1: Data Query Tools (16 Tools)

All tools are registered as Haseef tools. Gemini never calls these directly — it only calls `queue_thinker_task`.

### 1. `rafed_query` — General Natural Language SQL

The catch-all. Haseef translates the question to SQL, executes, returns results.

```yaml
name: rafed_query
description: "Ask any question about the Rafed school transport data. Haseef generates SQL, executes it, and returns the answer."
parameters:
  question:
    type: string
    required: true
    description: "Natural language question in Arabic or English"
  filters:
    type: object
    required: false
    properties:
      contract_id: string
      operator_id: string
      school_id: string
      vehicle_id: string
      driver_id: string
      date_from: string  # ISO date
      date_to: string    # ISO date
      sector_id: string
      administration_id: string
```

**Example:**
- Question: "كم حافلة بدون GPS في قطاع الرياض؟"
- Haseef generates: `SELECT COUNT(*) FROM v_current.dim_vehicle WHERE has_gps = false AND contract_id IN (SELECT contract_id FROM v_current.dim_contract WHERE sector_id = 'Riyadh')`
- Returns: `{ "count": 42 }`

### 2. `rafed_kpis` — Dashboard KPIs

```yaml
name: rafed_kpis
description: "Get current KPI dashboard snapshot."
parameters:
  contract_id: string (optional)
  operator_id: string (optional)
  sector_id: string (optional)
  date: string (optional)  # "today", "this_week", "this_month", or ISO date
```

**Returns:**
```json
{
  "total_schools": 11740,
  "total_students": 450000,
  "total_vehicles": 25512,
  "total_drivers": 28127,
  "vehicles_with_gps": 22100,
  "vehicles_without_gps": 3412,
  "accidents_this_month": 23,
  "inspection_pass_rate": 87.5,
  "seat_gap_total": -3400,
  "compliant_drivers_pct": 92.3,
  "active_contracts": 160,
  "open_complaints": 15
}
```

### 3. `rafed_schools` — School Search

```yaml
name: rafed_schools
description: "Search schools by name, sector, administration, contract."
parameters:
  search: string (optional)       # Name or ministerial number (partial)
  sector_id: string (optional)
  administration_id: string (optional)
  contract_id: string (optional)
  limit: integer (optional, default 20, max 100)
```

### 4. `rafed_vehicles` — Vehicle/Bus Search

```yaml
name: rafed_vehicles
description: "Search buses: plate, GPS, capacity, operator, expiry dates, special needs."
parameters:
  search: string (optional)              # Plate number or vehicle ID
  operator_id: string (optional)
  contract_id: string (optional)
  has_gps: boolean (optional)
  is_special_needs: boolean (optional)
  expiring_within_days: integer (optional)  # License/insurance/inspection
  limit: integer (optional, default 20, max 100)
```

### 5. `rafed_drivers` — Driver Search

```yaml
name: rafed_drivers
description: "Search drivers: name, nationality, license, training, compliance, age."
parameters:
  search: string (optional)
  operator_id: string (optional)
  contract_id: string (optional)
  is_saudi: boolean (optional)
  is_trained: boolean (optional)
  compliance_status: string (optional)  # "compliant", "non_compliant", "expiring"
  limit: integer (optional, default 20, max 100)
```

### 6. `rafed_accidents` — Accident Reports

```yaml
name: rafed_accidents
description: "Query accident reports with injuries, fatalities, location, driver info."
parameters:
  date_from: string (optional)
  date_to: string (optional)
  contract_id: string (optional)
  operator_id: string (optional)
  severity: string (optional)
  sector_id: string (optional)
  limit: integer (optional, default 20, max 100)
```

### 7. `rafed_inspections` — Inspection Results

```yaml
name: rafed_inspections
description: "Query inspection visits, scores, pass/fail, violations, detailed answers."
parameters:
  date_from: string (optional)
  date_to: string (optional)
  contract_id: string (optional)
  school_id: string (optional)
  inspector_id: string (optional)
  status: string (optional)       # "pass", "fail", "pending"
  include_answers: boolean (optional, default false)
  limit: integer (optional, default 20, max 100)
```

### 8. `rafed_compliance` — Compliance Status

```yaml
name: rafed_compliance
description: "Compliance across drivers, vehicles, contracts: expiry dates, training, points."
parameters:
  contract_id: string (optional)
  operator_id: string (optional)
  entity_type: string (optional)          # "drivers", "vehicles", "contracts", "all"
  expiring_within_days: integer (optional, default 30)
```

### 9. `rafed_seat_gaps` — Seat Gap Analysis

```yaml
name: rafed_seat_gaps
description: "Seat allocation vs actual: shortages, surpluses, gap percentage per school."
parameters:
  contract_id: string (optional)
  sector_id: string (optional)
  school_id: string (optional)
  only_gaps: boolean (optional, default true)  # Only show shortages
  limit: integer (optional, default 20, max 100)
```

### 10. `rafed_routes` — Route Planning

```yaml
name: rafed_routes
description: "Planned routes: school, vehicle, round number, students planned."
parameters:
  contract_id: string (optional)
  school_id: string (optional)
  vehicle_id: string (optional)
  limit: integer (optional, default 20, max 100)
```

### 11. `rafed_complaints` — Complaints

```yaml
name: rafed_complaints
description: "Complaints: date, category, severity, status, channel, resolution."
parameters:
  date_from: string (optional)
  date_to: string (optional)
  contract_id: string (optional)
  category: string (optional)
  status: string (optional)    # "open", "resolved", "pending"
  limit: integer (optional, default 20, max 100)
```

### 12. `rafed_safety_checks` — Safety Check Reports

```yaml
name: rafed_safety_checks
description: "Daily safety checks from drivers: pre-trip, post-trip, question answers, photos."
parameters:
  date_from: string (optional)
  date_to: string (optional)
  contract_id: string (optional)
  driver_id: string (optional)
  check_type: string (optional)   # "morning", "evening"
  limit: integer (optional, default 20, max 100)
```

### 13. `rafed_school_visits` — Bus Arrival/Departure

```yaml
name: rafed_school_visits
description: "Bus school visits: arrivals, departures, times, distances, GPS. Pre-aggregated for performance."
parameters:
  date_from: string (optional)
  date_to: string (optional)
  school_code: string (optional)
  contract_id: string (optional)
  event_type: string (optional)   # "arrival", "departure"
  limit: integer (optional, default 20, max 100)
```

### 14. `rafed_assignments` — Student Assignments

```yaml
name: rafed_assignments
description: "Student-to-bus assignments: school, vehicle, driver, distance, duration."
parameters:
  contract_id: string (optional)
  school_id: string (optional)
  vehicle_id: string (optional)
  driver_id: string (optional)
  limit: integer (optional, default 20, max 100)
```

### 15. `rafed_operators` — Operator Search

```yaml
name: rafed_operators
description: "Search transport operators/contractors: name, category, CR, contracts."
parameters:
  search: string (optional)
  contract_id: string (optional)
  is_sub: boolean (optional)
  limit: integer (optional, default 20, max 100)
```

### 16. `rafed_contracts` — Contract Details

```yaml
name: rafed_contracts
description: "Contract details: operator, sector, seats, amounts, dates, active status."
parameters:
  contract_id: string (optional)
  operator_id: string (optional)
  sector_id: string (optional)
  active_only: boolean (optional, default true)
  limit: integer (optional, default 20, max 100)
```

---

## Part 2: Interactive React Dashboard

Haseef controls a React frontend via WebSocket. It sends **render specs** (JSON) that the frontend interprets into visualizations.

### Frontend Tech Stack

```
React 18 + TypeScript + Vite
├── TailwindCSS          — styling
├── Recharts             — charts (bar, line, pie, area, scatter)
├── react-leaflet        — maps (school locations, bus routes, accident pins)
├── ag-grid-react        — data tables/grids (sorting, filtering, grouping)
├── lucide-react         — icons
├── shadcn/ui            — UI components (cards, tabs, dialogs, badges)
└── WebSocket            — real-time render spec stream from Haseef
```

### Render Spec Protocol

Haseef sends JSON render specs over WebSocket. The frontend has a component registry that maps spec types to React components.

```typescript
interface RenderSpec {
  id: string;              // unique widget ID
  type: WidgetType;        // which component to render
  title: string;           // widget title (Arabic or English)
  title_ar?: string;       // Arabic title
  data: any;               // data payload (chart data, table rows, etc.)
  config?: WidgetConfig;   // optional config (colors, axes, zoom, etc.)
  layout?: LayoutSpec;     // grid position, size
}

type WidgetType =
  | "kpi_cards"            // row of metric cards
  | "bar_chart"            // vertical/horizontal bars
  | "line_chart"           // time series
  | "pie_chart"            // donut/pie
  | "area_chart"           // stacked area
  | "scatter_plot"         // XY scatter
  | "data_table"           // sortable/filterable grid
  | "map"                  // Leaflet map with markers/heat/routes
  | "heatmap"              // calendar heatmap or grid heatmap
  | "funnel"               // funnel chart
  | "gauge"                // radial gauge (e.g., compliance %)
  | "stat_list"            // simple key-value list
  | "alert_list"           // highlighted warnings/issues
  | "tabs"                 // tabbed container with sub-widgets
  | "dashboard"            // full dashboard layout (multiple widgets)
  | "text_report"          // formatted text with highlights
  | "timeline"             // chronological events
  | "comparison"           // side-by-side comparison
  ;

interface LayoutSpec {
  column: number;          // grid column position
  row: number;             // grid row position
  width: number;           // span (1-12)
  height: number;          // span in rows
}

interface WidgetConfig {
  // Chart-specific
  xKey?: string;           // X axis data key
  yKeys?: string[];        // Y axis data keys (multiple series)
  colors?: string[];       // series colors
  stacked?: boolean;       // stacked bars/areas
  horizontal?: boolean;    // horizontal bars
  showLegend?: boolean;
  showGrid?: boolean;
  // Map-specific
  center?: [number, number];  // [lat, lng]
  zoom?: number;
  markers?: MapMarker[];
  heatmap?: boolean;
  route?: [[number, number]]; // polyline coordinates
  // Table-specific
  columns?: ColumnDef[];      // column definitions
  pageSize?: number;
  enableSorting?: boolean;
  enableFiltering?: boolean;
  enableGrouping?: boolean;
  // Gauge-specific
  min?: number;
  max?: number;
  thresholds?: { value: number; color: string }[];
  // KPI cards
  cards?: KPICard[];
}

interface MapMarker {
  lat: number;
  lng: number;
  label: string;
  label_ar?: string;
  color?: string;
  icon?: string;           // lucide icon name
  popup?: string;          // HTML content for popup
}

interface ColumnDef {
  key: string;
  label: string;
  label_ar?: string;
  type?: "text" | "number" | "date" | "boolean" | "badge" | "link";
  width?: number;
  format?: string;         // e.g., "currency_sar", "percentage", "date_ar"
}

interface KPICard {
  label: string;
  label_ar?: string;
  value: string | number;
  icon?: string;           // lucide icon name
  color?: string;          // tailwind color
  trend?: "up" | "down" | "flat";
  trend_value?: string;    // e.g., "+5.2%"
  sparkline?: number[];    // mini sparkline data
}
```

### UI Control Tools (Haseef → Frontend)

These are additional Haseef tools that control the React dashboard:

#### 17. `ui_render` — Render a Single Widget

```yaml
name: ui_render
description: "Render a single visualization widget on the dashboard."
parameters:
  widget:
    type: object
    required: true
    description: "RenderSpec object — type, title, data, config, layout"
  replace:
    type: boolean
    optional: true
    default: false
    description: "If true, replaces all current widgets. If false, adds alongside."
```

#### 18. `ui_dashboard` — Render Full Dashboard

```yaml
name: ui_dashboard
description: "Render a complete dashboard with multiple widgets in a grid layout."
parameters:
  title:
    type: string
    required: true
    description: "Dashboard title"
  title_ar:
    type: string
    optional: true
  widgets:
    type: array
    required: true
    description: "Array of RenderSpec objects with layout positions"
  layout_mode:
    type: string
    optional: true
    default: "grid"
    enum: ["grid", "tabs", "scroll", "split"]
```

#### 19. `ui_update_widget` — Update Existing Widget

```yaml
name: ui_update_widget
description: "Update data or config of an existing widget without re-rendering the whole dashboard."
parameters:
  widget_id:
    type: string
    required: true
  data:
    type: object
    optional: true
  config:
    type: object
    optional: true
```

#### 20. `ui_clear` — Clear Dashboard

```yaml
name: ui_clear
description: "Clear all widgets from the dashboard."
parameters: {}
```

#### 21. `ui_navigate` — Navigate to a View

```yaml
name: ui_navigate
description: "Navigate to a pre-built view or a specific school/vehicle/driver detail page."
parameters:
  view:
    type: string
    required: true
    enum:
      - "overview"           # main dashboard
      - "schools"            # schools list view
      - "vehicles"           # vehicles list view
      - "drivers"            # drivers list view
      - "accidents"          # accidents view
      - "inspections"        # inspections view
      - "compliance"         # compliance view
      - "routes"             # routes view
      - "complaints"         # complaints view
      - "school_detail"      # single school profile
      - "vehicle_detail"     # single vehicle profile
      - "driver_detail"      # single driver profile
      - "contract_detail"    # single contract profile
      - "operator_detail"    # single operator profile
  entity_id:
    type: string
    optional: true
    description: "ID for detail views (school_id, vehicle_id, driver_id, etc.)"
```

#### 22. `ui_highlight` — Highlight Data on Existing Widget

```yaml
name: ui_highlight
description: "Highlight specific data points on an existing chart/map/table. Useful when answering a question about a specific item shown on screen."
parameters:
  widget_id:
    type: string
    required: true
  highlights:
    type: array
    required: true
    items:
      type: object
      properties:
        key: string         # data key to match
        value: any          # value to match
        color: string       # highlight color
        label: string       # annotation label
```

#### 23. `ui_export` — Export Current View

```yaml
name: ui_export
description: "Export the current dashboard view as PDF, Excel, or image."
parameters:
  format:
    type: string
    required: true
    enum: ["pdf", "excel", "png"]
  filename:
    type: string
    optional: true
```

---

## Part 3: Visualization Examples

### Example 1: "كيف وضع النقل في الباحة؟" (General overview)

Haseef calls:
1. `rafed_kpis(sector_id="al_baha")` → gets KPIs
2. `ui_dashboard(title="لوحة معلومات النقل المدرسي - الباحة", title_ar="...", widgets=[...])`

**Rendered dashboard:**

```
┌─────────────────────────────────────────────────────────────┐
│  لوحة معلومات النقل المدرسي - الباحة                         │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  المدارس    │  الحافلات   │  السائقين   │  معدل التفتيش     │
│  ١١٬٧٤٠     │  ٢٥٬٥١٢     │  ٢٨٬١٢٧     │  ٨٧٫٥٪            │
│  📈 +12     │  📉 -3      │  📈 +45     │  📈 +2.1٪        │
├─────────────┴─────────────┴─────────────┴───────────────────┤
│  الحافلات بدون GPS                                          │
│  ████████████░░░░░░░░░░░░░░░░░░░░  ٣٤١٢ / ٢٥٥١٢            │
├─────────────────────────────────────────────────────────────┤
│  الحوادث (آخر ٦ أشهر)                                       │
│  📈 Line chart showing accident trend over 6 months         │
├──────────────────────────┬──────────────────────────────────┤
│  فجوات المقاعد           │  خريطة المدارس                   │
│  🔴 ٣٤٠٠ مقعد ناقص       │  🗺️ Map with school markers     │
│  Top 10 schools list     │  colored by seat gap status       │
└──────────────────────────┴──────────────────────────────────┘
```

**Render spec (JSON):**
```json
{
  "type": "dashboard",
  "title": "لوحة معلومات النقل المدرسي - الباحة",
  "layout_mode": "grid",
  "widgets": [
    {
      "id": "kpi_overview",
      "type": "kpi_cards",
      "title": "نظرة عامة",
      "layout": { "column": 0, "row": 0, "width": 12, "height": 1 },
      "config": {
        "cards": [
          { "label_ar": "المدارس", "value": 11740, "icon": "school", "color": "blue", "trend": "up", "trend_value": "+12" },
          { "label_ar": "الحافلات", "value": 25512, "icon": "bus", "color": "green", "trend": "down", "trend_value": "-3" },
          { "label_ar": "السائقين", "value": 28127, "icon": "users", "color": "purple", "trend": "up", "trend_value": "+45" },
          { "label_ar": "معدل التفتيش", "value": "87.5%", "icon": "clipboard-check", "color": "teal", "trend": "up", "trend_value": "+2.1%" }
        ]
      }
    },
    {
      "id": "gps_chart",
      "type": "bar_chart",
      "title": "الحافلات بدون GPS",
      "title_ar": "الحافلات بدون GPS",
      "layout": { "column": 0, "row": 1, "width": 12, "height": 2 },
      "data": [
        { "label": "مع GPS", "value": 22100 },
        { "label": "بدون GPS", "value": 3412 }
      ],
      "config": { "xKey": "label", "yKeys": ["value"], "colors": ["#22c55e", "#ef4444"], "horizontal": true }
    },
    {
      "id": "accident_trend",
      "type": "line_chart",
      "title": "الحوادث (آخر ٦ أشهر)",
      "title_ar": "الحوادث (آخر ٦ أشهر)",
      "layout": { "column": 0, "row": 3, "width": 6, "height": 3 },
      "data": [
        { "month": "يناير", "accidents": 18, "injuries": 5 },
        { "month": "فبراير", "accidents": 22, "injuries": 8 },
        { "month": "مارس", "accidents": 15, "injuries": 3 },
        { "month": "أبريل", "accidents": 19, "injuries": 6 },
        { "month": "مايو", "accidents": 23, "injuries": 9 },
        { "month": "يونيو", "accidents": 12, "injuries": 2 }
      ],
      "config": { "xKey": "month", "yKeys": ["accidents", "injuries"], "colors": ["#ef4444", "#f59e0b"], "showLegend": true }
    },
    {
      "id": "seat_gap_map",
      "type": "map",
      "title": "خريطة المدارس - فجوة المقاعد",
      "title_ar": "خريطة المدارس",
      "layout": { "column": 6, "row": 3, "width": 6, "height": 3 },
      "config": {
        "center": [20.0, 41.0],
        "zoom": 8,
        "markers": [
          { "lat": 20.01, "lng": 41.07, "label_ar": "مدرسة الأمل", "color": "#ef4444", "popup": "ناقص ٤٥ مقعد" },
          { "lat": 20.03, "lng": 41.05, "label_ar": "مدرسة النور", "color": "#22c55e", "popup": "فائض ١٢ مقعد" }
        ]
      }
    }
  ]
}
```

### Example 2: "أرني تفاصيل مدرسة الأمل" (School detail)

Haseef calls:
1. `rafed_schools(search="الأمل")` → gets school info
2. `rafed_assignments(school_id=...)` → gets student assignments
3. `rafed_inspections(school_id=...)` → gets inspection history
4. `rafed_seat_gaps(school_id=...)` → gets seat gap
5. `ui_dashboard(title="مدرسة الأمل", widgets=[...])`

**Rendered:**

```
┌─────────────────────────────────────────────────────────────┐
│  مدرسة الأمل الابتدائية                                      │
│  قطاع الباحة الشمالية | إدارة التعليم بالبلد                 │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ المقاعد      │ الطلاب       │ الحافلات     │ فجوة المقاعد   │
│ ٢٥٠          │ ٢٣٨          │ ٥            │ +١٢ فائض       │
├──────────────┴──────────────┴──────────────┴────────────────┤
│  سجل التفتيش                                                │
│  📋 Table: date | inspector | score | status | findings     │
├─────────────────────────────────────────────────────────────┤
│  الحافلات المعينة                                           │
│  🚌 Table: plate | driver | capacity | GPS | route          │
├─────────────────────────────────────────────────────────────┤
│  🗺️ Map showing school + bus routes + student home clusters │
└─────────────────────────────────────────────────────────────┘
```

### Example 3: "وش أكثر المشاكل اللي تطلع في التفتيش؟" (Inspection findings)

Haseef calls:
1. `rafed_query(question="top inspection failure categories")` → gets aggregated data
2. `ui_render(widget={ type: "pie_chart", ... })`

**Rendered:**
```
┌────────────────────────────────┐
│  أكثر مشاكل التفتيش            │
│                                │
│     🔴 الإطارات ٣٢٪            │
│   🟡 المكابح ٢٤٪               │
│  🟢 الأبواب ١٨٪                │
│   🔵 الإنارة ١٥٪               │
│  ⚪ أخرى ١١٪                   │
│                                │
│  [Pie/donut chart]             │
└────────────────────────────────┘
```

### Example 4: "أرني حوادث هذا الشهر على الخريطة" (Accident map)

Haseef calls:
1. `rafed_accidents(date_from="2026-06-01", date_to="2026-06-30")` → gets accidents with coordinates
2. `ui_render(widget={ type: "map", config: { markers: [...], heatmap: true } })`

**Rendered:**
```
┌─────────────────────────────────────────────────────┐
│  حوادث يونيو ٢٠٢٦                                  │
│                                                     │
│  🗺️ Interactive map:                               │
│     🔴 = fatal   🟠 = injury   🟡 = minor          │
│     Heatmap overlay showing accident density        │
│     Click pin → popup with accident details         │
│                                                     │
│  Total: 23 accidents | 8 injuries | 1 fatality     │
└─────────────────────────────────────────────────────┘
```

### Example 5: "قارن أداء مشغلين" (Operator comparison)

Haseef calls:
1. `rafed_operators()` → gets operators
2. `rafed_kpis(operator_id=...)` for each → gets KPIs
3. `ui_render(widget={ type: "comparison", ... })`

**Rendered:**
```
┌───────────────────────────────────────────────────────┐
│  مقارنة المشغلين                                      │
│                                                       │
│  ┌─────────────┐  vs  ┌─────────────┐                │
│  │ شركة النقل   │      │ شركة الحافلات│                │
│  │ الحافلات     │      │ الذهبية      │                │
│  ├─────────────┤      ├─────────────┤                │
│  │ حافلات: ٤٥٠ │      │ حافلات: ٣٢٠ │                │
│  │ GPS: ٩٨٪    │      │ GPS: ٧٦٪    │                │
│  │ امتثال: ٩٥٪ │      │ امتثال: ٨١٪ │                │
│  │ حوادث: ٣    │      │ حوادث: ٧    │                │
│  │ تفتيش: ٩٢٪  │      │ تفتيش: ٧٨٪  │                │
│  └─────────────┘      └─────────────┘                │
│                                                       │
│  📊 Side-by-side bar chart comparing all metrics     │
└───────────────────────────────────────────────────────┘
```

---

## Part 4: Implementation Plan

### Phase 1: Database Layer

```
Files:
  hsafa_robot/rafed_db.py          — asyncpg connection pool, query executor
  hsafa_robot/rafed_schema.py      — compact schema description for Haseef
  .env                             — RAFED_DB_URL=postgresql://readonly@localhost/rafed
```

**Tasks:**
- [ ] Restore `v_current` schema only into local PostgreSQL
- [ ] Create read-only database role
- [ ] Create indexes on FK columns
- [ ] Pre-aggregate large tables into `rafed_summary` schema
- [ ] Build `rafed_db.py` with asyncpg pool
- [ ] Build `rafed_schema.py` with compact table/column descriptions

### Phase 2: Query Tools

```
Files:
  hsafa_robot/rafed_tools.py       — 16 query tool implementations
  main.py                          — register tools in setup_haseef()
```

**Tasks:**
- [ ] Implement all 16 query tools
- [ ] Register in `setup_haseef()` with handlers
- [ ] Add safety: read-only, LIMIT 100, reject destructive SQL
- [ ] Add Arabic column preference logic
- [ ] Test each tool with sample questions

### Phase 3: React Dashboard

```
Files:
  dashboard/                       — React app (Vite + TypeScript)
  dashboard/src/App.tsx            — main app, WebSocket connection
  dashboard/src/components/        — widget components
    KpiCards.tsx
    BarChart.tsx
    LineChart.tsx
    PieChart.tsx
    AreaChart.tsx
    DataTable.tsx
    MapView.tsx
    Heatmap.tsx
    Gauge.tsx
    AlertList.tsx
    Timeline.tsx
    Comparison.tsx
    TextReport.tsx
    Dashboard.tsx
  dashboard/src/lib/
    websocket.ts                   — WebSocket client
    render_spec.ts                 — TypeScript types for RenderSpec
    component_registry.ts          — maps widget type → component
  dashboard/src/index.css          — TailwindCSS
```

**Tasks:**
- [ ] Scaffold Vite + React + TypeScript project
- [ ] Install: tailwindcss, recharts, react-leaflet, ag-grid-react, lucide-react, shadcn/ui
- [ ] Build WebSocket client that receives render specs
- [ ] Build component registry
- [ ] Implement each widget component
- [ ] Build dashboard grid layout
- [ ] Add RTL support for Arabic
- [ ] Add dark mode

### Phase 4: UI Control Tools

```
Files:
  hsafa_robot/ui_bridge.py         — WebSocket server, render spec sender
  main.py                          — register UI tools in setup_haseef()
```

**Tasks:**
- [ ] Build WebSocket server in Python (websockets or aiohttp)
- [ ] Implement `ui_render`, `ui_dashboard`, `ui_update_widget`, `ui_clear`, `ui_navigate`, `ui_highlight`, `ui_export`
- [ ] Register in `setup_haseef()` with handlers
- [ ] Connect Haseef query results → render spec generation
- [ ] Test end-to-end: question → query → render spec → dashboard

### Phase 5: Integration & Polish

**Tasks:**
- [ ] Update Gemini system prompt with all Haseef tools
- [ ] Add Arabic voice responses that reference what's on screen ("شوف اللوحة قدامك...")
- [ ] Add conversational context ("هل تريد أريك تفاصيل أكثر؟")
- [ ] Add proactive alerts (Haseef pushes dashboard updates when data changes)
- [ ] Add export functionality (PDF/Excel/PNG)
- [ ] Add multi-dashboard tabs (user can have multiple views open)
- [ ] Performance: cache common queries, pre-compute summaries

---

## Part 5: Pre-Aggregation Strategy

The 3 largest tables need pre-aggregation to avoid scanning millions of rows per query:

```sql
CREATE SCHEMA IF NOT EXISTS rafed_summary;

-- School visit daily summary (5.9M → ~50K rows)
CREATE TABLE rafed_summary.school_visit_daily AS
SELECT
  school_code,
  event_type,
  DATE(event_time) AS day,
  COUNT(*) AS visit_count,
  AVG(distance_m) AS avg_distance,
  MIN(event_time)::time AS first_event,
  MAX(event_time)::time AS last_event
FROM v_current.fact_school_visit
GROUP BY school_code, event_type, DATE(event_time);

-- Inspection answer summary (4.4M → ~20K rows)
CREATE TABLE rafed_summary.inspection_category_summary AS
SELECT
  contract_id,
  category_name,
  COUNT(*) AS total_answers,
  SUM(CASE WHEN inside = true THEN 1 ELSE 0 END) AS passed,
  SUM(CASE WHEN inside = false THEN 1 ELSE 0 END) AS failed,
  AVG(CASE WHEN is_solved = true THEN 1 ELSE 0 END) AS solve_rate
FROM v_current.fact_inspection_answer
GROUP BY contract_id, category_name;

-- Violence incident summary (2M → ~5K rows)
CREATE TABLE rafed_summary.violence_monthly AS
SELECT
  contract_id,
  sector_id,
  DATE_TRUNC('month', violence_date) AS month,
  violence_type_id,
  violence_category_id,
  COUNT(*) AS incident_count,
  COUNT(DISTINCT bus_serial) AS affected_buses
FROM v_current.fact_ins_violence
GROUP BY contract_id, sector_id, DATE_TRUNC('month', violence_date), violence_type_id, violence_category_id;

-- Add indexes
CREATE INDEX idx_sv_school ON rafed_summary.school_visit_daily(school_code);
CREATE INDEX idx_sv_date ON rafed_summary.school_visit_daily(day);
CREATE INDEX idx_ins_contract ON rafed_summary.inspection_category_summary(contract_id);
CREATE INDEX idx_viol_month ON rafed_summary.violence_monthly(month);
```

---

## Part 6: Safety & Security

- **Read-only database role** — `CREATE ROLE rafed_reader WITH LOGIN PASSWORD '...' READONLY;`
- **Query timeout** — 5 seconds max per query
- **Row limit** — `LIMIT 100` enforced on all queries
- **SQL injection prevention** — parameterized queries only, no string concatenation
- **Reject destructive SQL** — no `DELETE`, `UPDATE`, `DROP`, `TRUNCATE`, `ALTER`
- **Audit log** — log all queries with timestamp, user, question, SQL, row count
- **PII protection** — `student_name_hash`, `driver_nid_hash`, `card_number_hash` are already hashed in the schema. Never expose raw hashes to the user.
- **WebSocket auth** — token-based authentication for dashboard connection

---

## Part 7: Gemini System Prompt Update

Add to the "HASEEF'S TOOLS" section:

```
=== HASEEF'S DATA TOOLS (Rafed School Transport) ===
Haseef can answer ANY question about the school transport system:
- rafed_query(question): Ask any question — Haseef generates SQL and executes it
- rafed_kpis(): Get KPI dashboard (schools, buses, drivers, accidents, inspections)
- rafed_schools(search): Search schools by name, sector, area
- rafed_vehicles(search): Search buses — GPS, capacity, expiry dates, special needs
- rafed_drivers(search): Search drivers — license, training, compliance, nationality
- rafed_accidents(date_from, date_to): Accident reports with injuries, fatalities
- rafed_inspections(date_from, status): Inspection visits, scores, violations
- rafed_compliance(entity_type): License/insurance/inspection expiry, training status
- rafed_seat_gaps(): Seat allocation vs actual — shortages and surpluses
- rafed_routes(): Planned routes per school/vehicle
- rafed_complaints(date_from, category): Complaints with status and resolution
- rafed_safety_checks(date_from): Daily safety check reports from drivers
- rafed_school_visits(date_from): Bus arrivals/departures at schools
- rafed_assignments(): Student-to-bus assignments with distance
- rafed_operators(search): Search transport operators/contractors
- rafed_contracts(): Contract details — operator, seats, amounts, dates

=== HASEEF'S DASHBOARD TOOLS ===
Haseef can also SHOW data on the interactive dashboard:
- ui_dashboard(title, widgets): Show a full dashboard with charts, maps, tables
- ui_render(widget): Show a single chart/map/table
- ui_update_widget(widget_id, data): Update existing widget
- ui_clear(): Clear the dashboard
- ui_navigate(view): Go to a specific view (schools, vehicles, accidents, etc.)
- ui_highlight(widget_id, highlights): Highlight specific data on screen
- ui_export(format): Export current view as PDF/Excel/PNG

When the user asks about data, Haseef will BOTH answer verbally AND show
visualizations on the dashboard. You can reference what's on screen:
"شوف اللوحة قدامك، تلقى الرسم البياني واضح"
```

---

## Summary

| Layer | Count | Description |
|-------|-------|-------------|
| Data query tools | 16 | Haseef queries PostgreSQL, returns data |
| UI control tools | 7 | Haseef controls React dashboard |
| Widget types | 17 | Charts, maps, tables, KPIs, gauges, etc. |
| Total Haseef tools | 23 | All registered as Haseef tools |
| Gemini tools | 1 | `queue_thinker_task` only |

**Key principle:** Gemini is the voice. Haseef is the brain. The dashboard is the eyes.
