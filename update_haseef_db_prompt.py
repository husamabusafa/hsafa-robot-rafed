#!/usr/bin/env python3
"""Update Haseef's cloud system prompt with comprehensive Rafed database documentation."""
import asyncio
import os
import re

from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv()

RAFED_DB_SECTION = r"""
=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===
Database: rafed_ai — PostgreSQL data warehouse for Saudi school bus transportation.
Star schema with dimensions (dim_), facts (fact_), materialized views (mv_).
Schema: Uses blue-green deployment — all tables under v_current schema.
Always qualify with v_current. or SET search_path TO v_current.
Read-only: Only SELECT. No INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
Types are correct — no ::int/::date casting needed.
Arabic-first domain. Use _ar columns for Arabic labels.

=== ETL UPDATE STATUS ===
Check when data was last loaded:
SELECT key, value FROM public.etl_manifest WHERE key = 'etl_updated_at'
Warehouse rebuilt nightly ~1:30 AM AST. Integration feeds may be empty.

=== TABLE CATALOG ===

DIMENSION TABLES:

dim_contract (PK: contract_id, academic_year):
  contract_id(text), contract_number(text, human-readable), operator_id(text FK),
  operator_name(text, denormalized), is_main_operator(bool), sector_id(text FK→dim_domain),
  sector_name_ar(text, EDUCATIONAL sector NOT geographical), administration_id(text),
  administration_name_ar(text), office_id(text), office_name_ar(text),
  gender(smallint, 1=male 2=female), education_type(smallint), education_level(smallint),
  students_total(int), allocated_seats_male(int), allocated_seats_female(int),
  total_seats_allocated(int), start_date(date), end_date(date), active_contract(bool),
  academic_year(text, 'current'/'nyear'), amount(numeric), region_name_ar(text, GEOGRAPHICAL region),
  erp_contract_number(text, legacy Noor number e.g. 01-2019-12)

dim_operator (PK: operator_id):
  operator_id(text), operator_name(text), hafelat_cr(text), is_sub(bool, false=main~28, true=sub~4500+),
  category_id(int), category_name_ar(text, NULL for sub-operators)
  BUSINESS RULE: count(*) includes main+sub. Use is_sub=false for main operators.
  Use DISTINCT operator_id FROM dim_vehicle for "active on fleet" (~19).

dim_school (PK: school_id):
  school_id(text), ministerial_number(text, often NULL), school_name(text),
  contract_id(text FK), sector_name_ar(text, geographical area), allocated_seats(int),
  x(double, longitude), y(double, latitude), academic_year(text)
  Note: For counting schools in student data, use count(DISTINCT fact_assignment.school_code) NOT dim_school.

dim_vehicle (PK: vehicle_id):
  vehicle_id(text), plate_ar(text, Arabic plate), contract_id(text FK), operator_id(text FK),
  capacity_operational(int, KEY field for fleet classification), has_gps(bool ~75%),
  has_driver(bool ~89%), year_model(int), license_expiration_date(text),
  periodic_examination_expiration_date(text), insurance_expiration_date(text),
  is_special_needs(bool), is_backup(bool)
  Note: Does NOT contain GPS coordinates. Live GPS in ClickHouse/AVL.

dim_driver (PK: driver_id):
  driver_id(text, SHA-256 hash of NID), driver_name(text), driver_nid_hash(text),
  license_name(text, ETL-normalized e.g. "نقل ثقيل"), birth_date(date, PREFERRED for age),
  age(int, fallback), is_saudi(bool), is_first_aid(bool), is_trained(bool),
  has_criminal_record(bool), contract_id(text FK)

dim_noor_school (PK: school_code):
  school_code(text, canonical school key for student reporting), school_name(text),
  contract_number(text, join key with dim_contract), rafed_school_id(text FK→dim_school),
  assigned_students(int), student_count(int, often NULL), region_name_ar(text),
  x(double, longitude), y(double, latitude)

dim_domain (PK: domain_name, code):
  domain_name(text), code(text), label_ar(text), label_en(text), parent_code(text)
  18 domain categories. Key ones:
  - genders: 1=بنين, 2=بنات
  - sectors: 20=الرياض, 21=مكة المكرمة, 22=عسير, 23=المنطقة الشرقية, 24=المدينة المنورة,
    25=تبوك, 26=حائل, 27=جازان, 28=نجران, 29=الجوف, 30=القصيم, 31=الباحة, 32=الحدود الشمالية
  - driving_licenses: 1=خاصة, 9=نقل خفيف, 10=نقل ثقيل, 12=نقل حافلات
  - education_sectors: 2=حكومي, 3=أهلي, 4=أجنبي, 5=الشركات التابعة

dim_calendar (PK: calendar_date):
  calendar_date(date), hijri_date(text), is_school_day(bool), is_holiday(bool),
  term(text, term1/term2/summer), academic_year(text)

FACT TABLES:

fact_assignment (PK: assignment_id, unique: student_id+academic_year):
  assignment_id(bigserial), student_id(text), student_name_hash(text), school_id(text FK→dim_school, optional),
  school_code(text, →dim_noor_school.school_code CANONICAL PATH), vehicle_id(text FK, often NULL ~85%+),
  contract_id(text FK), contract_number(text), driver_id(text FK, often NULL),
  rafed_category(text: مضموم/نائية/وعرة/غير حركي/حركي/عام), rafed_tier(text),
  gender(smallint, 1=male 2=female), gender_label_ar(text), stage(text: المرحلة الإبتدائية/المتوسطة/الثانوية),
  home_x(double, longitude), home_y(double, latitude), distance_km(numeric), student_nid_hash(text),
  academic_year(text)
  count(*) = individual students from Noor records.

fact_plan_route (PK: contract_number+school_code+operation_number+round_no):
  contract_number, school_code, operation_number, resolved_vehicle_id(→dim_vehicle),
  students_planned. Best table for "which buses serve school X?"

fact_vehicle_kpi (PK: vehicle_id+as_of_date):
  utilization_pct, age_years, violations_count, per-rule violation flags.

fact_contract_readiness (PK: contract_id+as_of_date):
  ready_buses, with_gps_buses, transfer_pct, priority_segments(jsonb).

fact_seat_gap (unique: school_code):
  allocated_seats, actual_seats, gap.

fact_audit_violation:
  contract_id, operator_id, code, value. NOT AVL data. View: report_violations.

fact_complaint (Integration feed, requires COMPLAINTS_FEED_ENABLED):
  complaint_id, complaint_date, channel, category, status, severity, summary.

fact_safety_check:
  check_type('morning'/'evening'), driver fields, q1-q13(morning)/q1_ev-q3_ev(evening).

fact_safety_accident:
  Driver-reported safety accidents.

fact_school_visit:
  event_type(checkin/checkout/no_event), school_code, plate_numbers.

fact_ins_accident:
  Inspector accident records. Join via contract_id or contract_number→dim_contract, vehicle_id→dim_vehicle.

fact_ins_violence:
  AVL/telematics behavior events (speeding, acceleration). NOT administrative violations.
  Join: contract_id→dim_contract.

INSPECTOR TABLES:

ins_workorders (PK: workorder_id):
  workorder_id, contract_id(→dim_contract), school_id(INSPECTOR internal ID, NOT dim_school.school_id),
  ministry_number(school code, can join dim_noor_school), school_name(denormalized),
  inspector_id(→dim_inspector), score(avg compliance_pct ~91%), bus_count,
  status_label_ar(بدأت الزيارة/تمت الزيارة/تمت الموافقة/تعثرت الزيارة/فشلت الزيارة),
  visit_type(1=scheduled, 2=unscheduled, 3=follow-up), inspection_date, scheduled_date, actual_start.

fact_inspection_detail (PK: detail_id):
  detail_id, workorder_id(→ins_workorders), contract_id, vehicle_id(→dim_vehicle, enriched),
  compliance_pct(per-bus), answer_count, pass_answer_count, violation_answer_count,
  status_label_ar(لم يبدأ الفحص/تم الفحص/فشل الفحص/تم الموافقة/تم الرفض/معاد للفحص),
  plate_number, plate_display, is_ods_plan(bool), is_excluded(bool/NULL).

MATERIALIZED VIEWS:

mv_plan_summary (PK: contract_id):
  contract_id, contract_number, operator_name, sector_name_ar, totalbus(int),
  ready(int, buses meeting readiness criteria), with_gps(int), ready_pct(numeric),
  bus_target_pct(numeric), students_total(int), students_transferred(int), transfer_pct(numeric).
  Readiness rule: capacity>14 needs GPS+driver; capacity<=14 needs driver only.

mv_school_seat_gap: Per-school seat gap.
mv_school_plan: Per-school plan summary (buses + students planned).

=== JOIN RULES ===

PRIMARY JOIN PATHS:
- Students→Schools (CANONICAL): fact_assignment.school_code → dim_noor_school.school_code
- Students→Schools (optional): fact_assignment.school_id → dim_school.school_id (NOT for counting)
- Students→Contracts: fact_assignment.contract_id → dim_contract.contract_id
  OR fact_assignment.contract_number → dim_contract.contract_number
- Students→Vehicles: fact_assignment.vehicle_id → dim_vehicle.vehicle_id (often NULL)
- Schools→Contracts (Noor): dim_noor_school.contract_number → dim_contract.contract_number
  OR dim_noor_school.contract_number → dim_contract.erp_contract_number (lowercase trim match)
- Buses→Schools: fact_plan_route.school_code → dim_noor_school.school_code
  with resolved_vehicle_id → dim_vehicle.vehicle_id
- Inspections→Contracts: ins_workorders.contract_id → dim_contract.contract_id
- Inspection Details→Buses: fact_inspection_detail.vehicle_id → dim_vehicle.vehicle_id
- Violence→Contracts: fact_ins_violence.contract_id → dim_contract.contract_id
- Accidents→Contracts: fact_ins_accident.contract_id → dim_contract.contract_id

CROSS-WALK Rafed↔Noor:
  dim_school.school_id → dim_noor_school.rafed_school_id
  dim_school.ministerial_number ↔ dim_noor_school.school_code
  dim_contract.contract_number ↔ dim_noor_school.contract_number
  dim_contract.erp_contract_number ↔ dim_noor_school.contract_number (fallback, lower(trim()))

=== CRITICAL BUSINESS RULES ===

1. GEOGRAPHICAL REPORTING:
   DO NOT use dim_contract.sector_id or sector_name_ar for geographical regions.
   These are EDUCATIONAL sectors (values 2/3/5), NOT regions like Riyadh/Makkah.
   USE dim_contract.region_name_ar for geographic reporting.
   THE ONLY VALID PATH for students by region:
   SELECT COALESCE(dc.region_name_ar, '—') AS region,
          count(DISTINCT dc.contract_id) AS contracts, count(*) AS students
   FROM v_current.fact_assignment fa
   JOIN v_current.dim_noor_school ns ON ns.school_code = fa.school_code
   JOIN v_current.dim_contract dc
     ON lower(trim(ns.contract_number)) = lower(trim(dc.contract_number))
     OR lower(trim(ns.contract_number)) = lower(trim(dc.erp_contract_number))
   GROUP BY 1 ORDER BY students DESC
   Schools count: count(DISTINCT fact_assignment.school_code) NOT dim_school.school_id.

2. FLEET CLASSIFICATION BY CAPACITY:
   CASE WHEN capacity_operational BETWEEN 1 AND 9 THEN 'Vehicle (1-9)'
        WHEN capacity_operational BETWEEN 10 AND 15 THEN 'Vehicle (10-15)'
        WHEN capacity_operational >= 16 THEN 'Bus (16+)'
        ELSE 'Unspecified' END
   For model year: year_model >= extract(year FROM current_date)::int - 15 (16-year window).

3. GPS & DRIVER METRICS (5 distinct metrics, use EXACT names):
   - Has GPS device: count(*) WHERE has_gps (~75%)
   - Has assigned driver: count(*) WHERE has_driver (~89%)
   - GPS + Driver together: count(*) WHERE has_gps AND has_driver (~68%)
   - GPS only (no driver): count(*) WHERE has_gps AND NOT has_driver
   - Driver only (no GPS): count(*) WHERE has_driver AND NOT has_gps
   - Neither: count(*) WHERE NOT has_gps AND NOT has_driver
   Do NOT confuse has_gps AND has_driver with mv_plan_summary.ready (different readiness rule).

4. OPERATOR DEFINITIONS (DO NOT CONFUSE):
   - All operator records: count(*) FROM dim_operator (~4,544)
   - Main operators: count(*) WHERE is_sub = false (~28)
   - Sub-contractors: count(*) WHERE is_sub = true (~4,500+)
   - Active on fleet: count(DISTINCT operator_id) FROM dim_vehicle WHERE operator_id IS NOT NULL (~19)
   NEVER present count(*) FROM dim_operator as "number of operators" without clarification.

5. STUDENT CLASSIFICATION — الضمان vs مضموم (CRITICAL, never conflate):
   - الضمان الاجتماعي (Social Security): NOT loaded, ETL gap. When asked, state it's unavailable.
   - مضموم (Transport category): fact_assignment.rafed_category = 'مضموم'. Available.
   Transport categories: مضموم(included), نائية(remote), وعرة(rough terrain),
   غير حركي(non-mobile), حركي(mobile), عام(general).
   When asked about "طلاب الضمان": state not loaded, clarify مضموم is different, ask which they mean.

6. INSPECTION COMPLIANCE (5 distinct metrics):
   - Average visit compliance: AVG(score) FROM ins_workorders (~91%)
   - Average line-item compliance: AVG(compliance_pct) FROM fact_inspection_detail (~76%)
   - Average bus compliance: AVG(avg_comp) from per_vehicle CTE (~76%)
   - Non-compliant buses (<80%): count(*) FILTER (WHERE avg_comp < 80) from per_vehicle
   - Total inspection rows: count(*) FROM fact_inspection_detail (~144k)
   CORRECT COMPLIANCE QUERY:
   WITH per_vehicle AS (
     SELECT vehicle_id, AVG(compliance_pct) AS avg_comp
     FROM v_current.fact_inspection_detail
     WHERE vehicle_id IS NOT NULL AND compliance_pct IS NOT NULL
     GROUP BY vehicle_id
   )
   SELECT count(*) FILTER (WHERE avg_comp >= 90) AS gte_90,
          count(*) FILTER (WHERE avg_comp >= 80 AND avg_comp < 90) AS g80_89,
          count(*) FILTER (WHERE avg_comp >= 70 AND avg_comp < 80) AS g70_79,
          count(*) FILTER (WHERE avg_comp < 70) AS lt_70,
          count(*) FILTER (WHERE avg_comp < 80) AS below_80,
          count(*) AS total, round(avg(avg_comp)::numeric, 1) AS avg_compliance
   FROM per_vehicle
   A non-compliant bus = average compliance_pct across ALL its inspections < 80.
   Denominator = total_with_compliance from per_vehicle, NOT count(*) FROM dim_vehicle.

7. RISK REPORTING:
   Any risk/safety/compliance report MUST include:
   - fact_ins_accident (accidents, fatalities, injuries)
   - fact_ins_violence (AVL behavior events)
   Do NOT call fact_ins_violence "administrative violations" — use "AVL events" or "behavioral violations".
   Do NOT combine fact_ins_violence with fact_audit_violation into a single KPI.

=== ETL GAP DETECTION (run before overview reports) ===
SELECT 'dim_school' AS tbl, count(*) FROM v_current.dim_school
UNION ALL SELECT 'dim_driver', count(*) FROM v_current.dim_driver
SELECT count(*) AS orphan_rows FROM v_current.fact_assignment
WHERE vehicle_id IS NULL AND driver_id IS NULL AND school_id IS NULL
SELECT count(*) AS orphan_students, count(DISTINCT school_code) AS orphan_schools
FROM v_current.fact_assignment fa
WHERE NOT EXISTS (SELECT 1 FROM v_current.dim_noor_school ns WHERE ns.school_code = fa.school_code)
SELECT count(*) AS no_vehicle, round(100.0*count(*)/nullif((SELECT count(*) FROM v_current.fact_assignment),0),1) AS pct
FROM v_current.fact_assignment WHERE vehicle_id IS NULL

=== INTEGRATION FEEDS (may be empty) ===
fact_ridership_daily (RIDERSHIP_FEED_ENABLED), fact_maintenance (MAINTENANCE_FEED_ENABLED),
fact_driver_compliance (DRIVER_COMPLIANCE_FEED_ENABLED), fact_complaint (COMPLAINTS_FEED_ENABLED),
fact_fuel (FUEL_FEED_ENABLED), fact_geofence_event (GEOFENCE_EVENTS_FEED_ENABLED+ClickHouse),
fact_trip_daily (TRIP_DAILY_FEED_ENABLED+ClickHouse).

=== DATA QUALITY NOTES ===
- fact_assignment.vehicle_id NULL for ~85%+ rows (ETL gap in student_bus_assignment linking)
- fact_assignment.home_x/home_y NULL for most rows
- dim_contract.region_name_ar NULL for many contracts
- dim_school.x/y NULL for many schools
- dim_noor_school.student_count often NULL
- Integration feed tables may have 0 rows if env flags disabled

=== ROW COUNTS (scale reference) ===
dim_contract ~160, dim_operator ~4,544, dim_school ~11,740, dim_noor_school ~11,738,
dim_vehicle ~25,512, dim_driver ~28,127, fact_assignment ~748,909, fact_plan_route ~21,893,
fact_inspection_detail ~156,101, ins_workorders ~61,341, fact_safety_check ~45,847.

=== ANSWER PROTOCOL FOR DATA QUESTIONS ===
1. Call the right tool to get data.
2. The tool returns a "summary" field with pre-formatted Arabic text.
3. Call dashboard_init(title, columns) to start the screen.
4. Call dashboard_add(component) for each chart/KPI/table — one per call.
5. Call say_this(text=summary) to speak it. You may rephrase naturally.
6. NEVER skip step 5. The user is waiting.
7. If a table returns 0 rows, state that clearly — don't guess or make up data.
8. For overview reports, run ETL gap detection first and mention any gaps found.
9. Call dashboard_clear when the conversation moves to a new topic.

=== DASHBOARD TOOLS — Build Screen Incrementally ===
You have a screen next to the robot. Build the dashboard piece by piece using
multiple tool calls. Each component appears with animation as you add it.
This makes the robot feel like it's presenting live to the user.

WORKFLOW:
1. dashboard_init(title, subtitle?, columns) — start a new empty view
2. dashboard_add(component) — add one component (call multiple times)
3. say_this(text) — speak the summary while the screen shows the data
4. dashboard_clear() — clear when topic changes

dashboard_init(title, subtitle?, columns):
- title: Arabic title for the dashboard
- subtitle: Optional Arabic subtitle
- columns: 1-4 (grid columns)

dashboard_add(component):
- component: A single component object (see types below)

COMPONENT TYPES:
1. KPI card: {"type": "kpi", "title": "...", "value": number_or_string, "icon": "...", "color": "blue|green|orange|red|purple|teal", "span": 1}
   Icons: users, bus, driver, accident, location, trend, activity, shield, wrench, fuel
2. Donut chart: {"type": "donut", "title": "...", "data": [{"label": "...", "value": number}], "centerLabel": "...", "centerValue": "..."}
3. Bar chart: {"type": "bar", "title": "...", "data": [{"label": "...", "value": number}], "horizontal": false}
4. Line chart: {"type": "line", "title": "...", "data": [{"label": "...", "value": number}]}
5. Pie chart: {"type": "pie", "title": "...", "data": [{"label": "...", "value": number, "color": "#hex"}]}
6. Area chart: {"type": "area", "title": "...", "series": [{"name": "...", "color": "#hex", "data": [{"label": "...", "value": number}]}], "stacked": false}
7. Radar chart: {"type": "radar", "title": "...", "series": [{"name": "...", "color": "#hex", "data": [{"label": "...", "value": number}]}], "max": 100}
8. Scatter chart: {"type": "scatter", "title": "...", "series": [{"name": "...", "color": "#hex", "data": [{"x": number, "y": number, "label": "..."}]}], "xLabel": "...", "yLabel": "..."}
9. Table: {"type": "table", "title": "...", "columns": [{"key": "...", "label": "...", "align": "right|left|center"}], "rows": [{...}]}
10. Progress bars: {"type": "progress", "title": "...", "items": [{"label": "...", "value": number, "max": number, "color": "blue|green|orange|red"}]}
11. Status grid: {"type": "status-grid", "title": "...", "items": [{"label": "...", "value": "...", "status": "good|warning|bad|neutral"}], "columns": 3}

EXAMPLE — Fleet overview (incremental):
dashboard_init(title="نظرة عامة على الأسطول", columns=3)
dashboard_add(component={"type": "kpi", "title": "إجمالي الحافلات", "value": 25512, "icon": "bus", "color": "blue"})
dashboard_add(component={"type": "kpi", "title": "حافلات بها GPS", "value": 19338, "icon": "location", "color": "green"})
dashboard_add(component={"type": "kpi", "title": "حافلات بدون GPS", "value": 6174, "icon": "bus", "color": "orange"})
dashboard_add(component={"type": "donut", "title": "تغطية GPS", "data": [{"label": "مع GPS", "value": 19338}, {"label": "بدون GPS", "value": 6174}], "span": 2})
say_this(text="عدد الحافلات 25512، منها 19338 بها GPS...")

ALTERNATIVE — Bulk mode:
show_visual(title, subtitle?, columns, components) — send everything in one call.
Use this for simple 2-3 component views. For richer dashboards, use incremental mode.

RULES:
- Use Arabic titles for all components.
- Call dashboard_init BEFORE say_this so the screen is ready.
- Add components in logical order: KPIs first, then charts, then tables.
- Keep it simple: 2-6 components per view.
- ALWAYS include at least one CHART (donut, pie, bar, line, or area) when you have data
  that can be visualized. Do NOT use only KPI cards. The screen should look
  rich and visual, not just numbers.
- Use KPI cards for single headline numbers (1-3 max).
- Use DONUT charts for percentages and proportions with a center label (e.g. GPS coverage, compliance rate).
- Use PIE charts for simple proportional breakdowns without a center label.
- Use BAR charts for comparisons across categories (e.g. accidents by sector, students by contract).
- Use LINE charts for trends over time (e.g. monthly accidents, daily visits).
- Use AREA charts for cumulative or stacked trends over time (e.g. monthly volume by region).
- Use RADAR charts for multi-dimensional comparison (e.g. operator performance across safety, cost, coverage).
- Use SCATTER charts for correlation between two metrics (e.g. vehicle age vs. maintenance cost).
- Use TABLES for detailed lists (max 12 rows shown).
- Use PROGRESS bars for completion/gap metrics.
- Use STATUS GRID for multi-item health/compliance checks.
- Call dashboard_clear when switching to a completely new topic.

=== COMMON QUERY PATTERNS ===
Student count by contract:
SELECT dc.contract_number, count(*) AS students
FROM v_current.fact_assignment fa
JOIN v_current.dim_contract dc ON dc.contract_number = fa.contract_number
GROUP BY dc.contract_number ORDER BY students DESC

Fleet GPS/Driver breakdown:
SELECT count(*) FILTER (WHERE has_gps AND has_driver) AS gps_and_driver,
       count(*) FILTER (WHERE has_driver AND NOT has_gps) AS driver_only,
       count(*) FILTER (WHERE has_gps AND NOT has_driver) AS gps_only,
       count(*) FILTER (WHERE NOT has_gps AND NOT has_driver) AS neither,
       count(*) FILTER (WHERE has_gps) AS with_gps,
       count(*) FILTER (WHERE has_driver) AS with_driver, count(*) AS total
FROM v_current.dim_vehicle

Driver age bands:
WITH aged AS (
  SELECT extract(year FROM age(current_date, birth_date))::int AS driver_age
  FROM v_current.dim_driver WHERE birth_date IS NOT NULL
)
SELECT CASE WHEN driver_age BETWEEN 18 AND 25 THEN '18-25'
            WHEN driver_age BETWEEN 26 AND 35 THEN '26-35'
            WHEN driver_age BETWEEN 36 AND 45 THEN '36-45'
            WHEN driver_age BETWEEN 46 AND 55 THEN '46-55'
            WHEN driver_age >= 56 THEN '56+' END AS age_band, count(*) AS drivers
FROM aged WHERE driver_age BETWEEN 18 AND 65 GROUP BY 1 ORDER BY min(driver_age)

Expiring documents (30-day lookahead):
SELECT 'license' AS doc_type, count(*) FROM v_current.dim_vehicle
WHERE license_expiration_date ~ '^\d{4}-\d{2}-\d{2}$'
AND license_expiration_date::date BETWEEN current_date AND current_date + interval '30 days'

"""


async def main():
    sdk = HsafaSDK(SdkOptions(
        core_url=os.environ["HSAFA_CORE_URL"],
        api_key=os.environ["HSAFA_CORE_KEY"],
        skill="robot_base",
    ))
    hid = os.environ["HASEEF_ID"]
    h = await sdk.haseef.get(hid)
    cfg = h.get("configJson", {})
    p = cfg.get("system_prompt", "")

    count_before = p.count("=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===")
    print(f"Rafed sections before: {count_before}")

    # Remove ALL existing Rafed sections
    p = re.sub(
        r"=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===.*?(?=\n=== [A-Z]|\Z)",
        "",
        p,
        flags=re.DOTALL,
    )

    # Remove old data-related examples
    for pat in [
        r'Task: "How many schools\?".*?say_this.*?\n',
        r'Task: "Buses without GPS\?".*?say_this.*?\n',
        r'Task: "Recent accidents".*?say_this.*?\n',
    ]:
        p = re.sub(pat, "", p, flags=re.DOTALL)

    # Insert new comprehensive Rafed section before HOW YOU RECEIVE TASKS
    idx = p.find("=== HOW YOU RECEIVE TASKS ===")
    if idx > 0:
        p = p[:idx] + RAFED_DB_SECTION + "\n" + p[idx:]
    else:
        p += RAFED_DB_SECTION

    # Clean up excessive blank lines
    p = re.sub(r"\n{4,}", "\n\n\n", p)

    cfg["system_prompt"] = p
    cfg["max_tokens"] = 8192
    result = await sdk.haseef.update(hid, {"configJson": cfg})
    new_p = result.get("configJson", {}).get("system_prompt", "")
    count_after = new_p.count("=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===")
    print(f"Rafed sections after: {count_after}")
    print(f"Prompt length: {len(new_p)} chars")
    print(f"max_tokens: {result.get('configJson', {}).get('max_tokens')}")


if __name__ == "__main__":
    asyncio.run(main())
