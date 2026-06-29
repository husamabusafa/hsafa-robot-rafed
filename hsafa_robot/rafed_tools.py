"""rafed_tools.py — Haseef tool definitions and handlers for the Rafed data warehouse.

Each tool is registered with Haseef so the brain can query the school transport
database.  Gemini never calls these directly — it only calls queue_thinker_task.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import rafed_db

log = logging.getLogger("rafed_tools")

SCHEMA = "v_current"

# Callback set by main.py — called with text to speak via Gemini
_say_callback = None


def set_say_callback(cb):
    """Register a coroutine callback: await cb(text) to speak via Gemini."""
    global _say_callback
    _say_callback = cb


async def _auto_speak(text: str) -> None:
    """If a say callback is registered, speak the text directly."""
    if not text:
        return
    if _say_callback is None:
        log.warning("[rafed_tools] auto-speak skipped — no callback registered")
        return
    try:
        log.info("[rafed_tools] auto-speak calling callback: %s", text[:80])
        await _say_callback(text)
    except Exception as exc:
        log.warning("[rafed_tools] auto-speak failed: %s", exc)

# ---------------------------------------------------------------------------
# Tool definitions (for haseef_sdk.register_tools)
# ---------------------------------------------------------------------------
TOOL_DEFS: List[Dict[str, Any]] = [
    # 1. rafed_query — general NL-to-SQL
    {
        "name": "rafed_query",
        "description": (
            "Ask any question about the Rafed school transport data warehouse. "
            "You generate SQL, execute it against the PostgreSQL database, and "
            "return the results. The database has schools, buses, drivers, "
            "contracts, accidents, inspections, assignments, routes, complaints, "
            "safety checks, and more. Always prefix tables with v_current. "
            "Use _ar columns when answering in Arabic. LIMIT results to 100 max. "
            "Only SELECT queries allowed.\n\n"
            + rafed_db.SCHEMA_DESCRIPTION
        ),
        "input": {
            "sql": "string",
            "description": "string?",
        },
    },
    # 2. rafed_kpis
    {
        "name": "rafed_kpis",
        "description": (
            "Get current KPI dashboard: total schools, students, buses, drivers, "
            "accidents, inspection pass rate, seat gaps, compliance. "
            "Pre-aggregated for speed."
        ),
        "input": {
            "contract_id": "string?",
            "operator_id": "string?",
            "sector_id": "string?",
        },
    },
    # 3. rafed_schools
    {
        "name": "rafed_schools",
        "description": (
            "Search and list schools with details: name, location, sector, "
            "administration, allocated seats, contract, operator. "
            "Supports text search and area filters."
        ),
        "input": {
            "search": "string?",
            "sector_id": "string?",
            "administration_id": "string?",
            "contract_id": "string?",
            "limit": "integer?",
        },
    },
    # 4. rafed_vehicles
    {
        "name": "rafed_vehicles",
        "description": (
            "Search buses/vehicles: plate number, GPS status, capacity, operator, "
            "contract, license/insurance/inspection expiry, special needs capacity."
        ),
        "input": {
            "search": "string?",
            "operator_id": "string?",
            "contract_id": "string?",
            "has_gps": "boolean?",
            "is_special_needs": "boolean?",
            "expiring_within_days": "integer?",
            "limit": "integer?",
        },
    },
    # 5. rafed_drivers
    {
        "name": "rafed_drivers",
        "description": (
            "Search drivers: name, nationality, license type/expiry, Saudi status, "
            "training, first aid, criminal record, compliance, traffic points, age."
        ),
        "input": {
            "search": "string?",
            "operator_id": "string?",
            "contract_id": "string?",
            "is_saudi": "boolean?",
            "is_trained": "boolean?",
            "compliance_status": "string?",
            "limit": "integer?",
        },
    },
    # 6. rafed_accidents
    {
        "name": "rafed_accidents",
        "description": (
            "Query accident reports: date, type, severity, injuries, fatalities, "
            "location, driver info, vehicle info. Supports date range and "
            "contract/sector filters."
        ),
        "input": {
            "date_from": "string?",
            "date_to": "string?",
            "contract_id": "string?",
            "operator_id": "string?",
            "sector_id": "string?",
            "limit": "integer?",
        },
    },
    # 7. rafed_inspections
    {
        "name": "rafed_inspections",
        "description": (
            "Query inspection visits and results: school, inspector, score, "
            "pass/fail, violations, status, findings. Can include detailed "
            "inspection answers."
        ),
        "input": {
            "date_from": "string?",
            "date_to": "string?",
            "contract_id": "string?",
            "school_id": "string?",
            "inspector_id": "string?",
            "status": "string?",
            "include_answers": "boolean?",
            "limit": "integer?",
        },
    },
    # 8. rafed_compliance
    {
        "name": "rafed_compliance",
        "description": (
            "Get compliance status across drivers, vehicles, and contracts: "
            "license expiry, insurance expiry, inspection expiry, training status, "
            "traffic points, operational cards."
        ),
        "input": {
            "contract_id": "string?",
            "operator_id": "string?",
            "entity_type": "string?",
            "expiring_within_days": "integer?",
        },
    },
    # 9. rafed_seat_gaps
    {
        "name": "rafed_seat_gaps",
        "description": (
            "Get seat gap analysis: allocated vs actual seats per school, "
            "shortage/surplus, gap percentage. Identifies schools needing more buses."
        ),
        "input": {
            "contract_id": "string?",
            "sector_id": "string?",
            "school_id": "string?",
            "only_gaps": "boolean?",
            "limit": "integer?",
        },
    },
    # 10. rafed_routes
    {
        "name": "rafed_routes",
        "description": (
            "Get planned routes: school, vehicle, round number, students planned. "
            "Supports contract and school filters."
        ),
        "input": {
            "contract_id": "string?",
            "school_id": "string?",
            "vehicle_id": "string?",
            "limit": "integer?",
        },
    },
    # 11. rafed_complaints
    {
        "name": "rafed_complaints",
        "description": (
            "Query complaints: date, category, severity, status, channel, "
            "resolution. Supports contract and date filters."
        ),
        "input": {
            "date_from": "string?",
            "date_to": "string?",
            "contract_id": "string?",
            "category": "string?",
            "status": "string?",
            "limit": "integer?",
        },
    },
    # 12. rafed_safety_checks
    {
        "name": "rafed_safety_checks",
        "description": (
            "Query daily safety check reports from drivers: pre-trip and post-trip "
            "inspections, question answers, photo evidence."
        ),
        "input": {
            "date_from": "string?",
            "date_to": "string?",
            "contract_id": "string?",
            "driver_id": "string?",
            "check_type": "string?",
            "limit": "integer?",
        },
    },
    # 13. rafed_school_visits
    {
        "name": "rafed_school_visits",
        "description": (
            "Query school visit records: bus arrivals and departures, times, "
            "distances, GPS coordinates."
        ),
        "input": {
            "date_from": "string?",
            "date_to": "string?",
            "school_code": "string?",
            "contract_id": "string?",
            "event_type": "string?",
            "limit": "integer?",
        },
    },
    # 14. rafed_assignments
    {
        "name": "rafed_assignments",
        "description": (
            "Query student-to-bus assignments: school, vehicle, driver, distance, "
            "duration, gender, tier, category."
        ),
        "input": {
            "contract_id": "string?",
            "school_id": "string?",
            "vehicle_id": "string?",
            "driver_id": "string?",
            "limit": "integer?",
        },
    },
    # 15. rafed_operators
    {
        "name": "rafed_operators",
        "description": (
            "Search transport operators/contractors: name, category, sub-operator "
            "status, CR number, associated contracts."
        ),
        "input": {
            "search": "string?",
            "contract_id": "string?",
            "is_sub": "boolean?",
            "limit": "integer?",
        },
    },
    # 17. show_visual — push a complete dashboard layout (bulk mode)
    {
        "name": "show_visual",
        "description": (
            "Display a complete visual dashboard on the robot's screen in one call. "
            "Use this for simple views with few components. "
            "For richer dashboards, use dashboard_init + dashboard_add instead. "
            "Components: kpi, donut, pie, bar, line, area, radar, scatter, "
            "table, progress, status-grid. "
            "Layout columns: 1-4. Each component can span multiple columns."
        ),
        "input": {
            "title": "string",
            "subtitle": "string?",
            "columns": "integer",
            "components": "array",
        },
    },
    # 18. dashboard_init — start a new dashboard view (incremental mode)
    {
        "name": "dashboard_init",
        "description": (
            "Start a new empty dashboard on the robot's screen. "
            "Call this FIRST, then add components one by one with dashboard_add. "
            "Each component appears with animation as you add it. "
            "This makes the robot feel like it's building the presentation live. "
            "Call this BEFORE say_this so the screen is ready while you speak."
        ),
        "input": {
            "title": "string",
            "subtitle": "string?",
            "columns": "integer",
        },
    },
    # 19. dashboard_add — add one component to the current dashboard
    {
        "name": "dashboard_add",
        "description": (
            "Add a single component to the dashboard on screen. "
            "The component appears immediately with animation. "
            "Call dashboard_init first, then call this multiple times to build "
            "the view piece by piece. Each call adds one component. "
            "Component types: kpi, donut, pie, bar, line, area, radar, scatter, "
            "table, progress, status-grid."
        ),
        "input": {
            "component": "object",
        },
    },
    # 20. dashboard_clear — clear the dashboard screen
    {
        "name": "dashboard_clear",
        "description": (
            "Clear the dashboard screen. Use when the conversation moves "
            "to a new topic and the old visuals are no longer relevant."
        ),
        "input": {},
    },
    # 16. rafed_contracts
    {
        "name": "rafed_contracts",
        "description": (
            "Get contract details: operator, sector, administration, seats "
            "allocated/reversed, amounts, dates, active status, region."
        ),
        "input": {
            "contract_id": "string?",
            "operator_id": "string?",
            "sector_id": "string?",
            "active_only": "boolean?",
            "limit": "integer?",
        },
    },
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _limit(args: Dict[str, Any], default: int = 20, maximum: int = 100) -> int:
    n = int(args.get("limit") or default)
    return max(1, min(n, maximum))


def _where(conditions: List[str]) -> str:
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


def _compact_summary(rows: List[Dict[str, Any]], max_rows: int = 10) -> str:
    """Build a compact text summary of query results for Haseef to speak."""
    if not rows:
        return "لا توجد نتائج."
    lines = []
    for r in rows[:max_rows]:
        parts = []
        for k, v in r.items():
            if v is not None and v != "":
                parts.append(f"{k}: {v}")
        lines.append(" | ".join(parts))
    header = f"({len(rows)} صف)"
    return header + "\n" + "\n".join(lines)


# --- 1. rafed_query ---------------------------------------------------------
async def handle_rafed_query(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    sql = args.get("sql", "").strip()
    if not sql:
        return {"ok": False, "error": "Missing 'sql' parameter"}
    desc = args.get("description", "")
    try:
        rows = await rafed_db.execute_query(sql)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "description": desc, "rows": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        log.error("[rafed_query] error: %s", exc)
        return {"ok": False, "error": str(exc), "sql": sql}


# --- 2. rafed_kpis ----------------------------------------------------------
async def handle_rafed_kpis(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    contract_id = args.get("contract_id")
    try:
        if contract_id:
            row = await rafed_db.execute_one(
                f"SELECT "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_school WHERE contract_id=$1) AS schools, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_vehicle WHERE contract_id=$1) AS vehicles, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_vehicle WHERE contract_id=$1 AND has_gps=true) AS vehicles_gps, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_driver WHERE contract_id=$1) AS drivers, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_contract WHERE contract_id=$1 AND active_contract=true) AS contracts, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.fact_ins_accident WHERE contract_id=$1) AS accidents, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.fact_complaint WHERE contract_id=$1 AND status NOT IN ('resolved','closed')) AS complaints, "
                f"(SELECT COALESCE(SUM(gap),0) FROM {SCHEMA}.fact_seat_gap WHERE contract_id=$1) AS seat_gap",
                (contract_id,),
            )
        else:
            row = await rafed_db.execute_one(
                f"SELECT "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_school) AS schools, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_vehicle) AS vehicles, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_vehicle WHERE has_gps=true) AS vehicles_gps, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_driver) AS drivers, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.dim_contract WHERE active_contract=true) AS contracts, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.fact_ins_accident) AS accidents, "
                f"(SELECT COUNT(*) FROM {SCHEMA}.fact_complaint WHERE status NOT IN ('resolved','closed')) AS complaints, "
                f"(SELECT COALESCE(SUM(gap),0) FROM {SCHEMA}.fact_seat_gap) AS seat_gap"
            )
        if not row:
            return {"ok": False, "error": "No data"}
        s = row.get("schools", 0)
        v = row.get("vehicles", 0)
        vg = row.get("vehicles_gps", 0)
        d = row.get("drivers", 0)
        c = row.get("contracts", 0)
        a = row.get("accidents", 0)
        cm = row.get("complaints", 0)
        sg = row.get("seat_gap", 0)
        summary = (
            f"عدد المدارس: {s}، الحافلات: {v} (مع GPS: {vg}، بدون: {v - vg})، "
            f"السائقين: {d}، العقود النشطة: {c}، الحوادث: {a}، "
            f"الشكاوى المفتوحة: {cm}، فجوة المقاعد: {sg}"
        )
        await _auto_speak(summary)
        return {
            "ok": True,
            "summary": summary,
            "kpis": {
                "total_schools": s,
                "total_vehicles": v,
                "vehicles_with_gps": vg,
                "vehicles_without_gps": v - vg,
                "total_drivers": d,
                "active_contracts": c,
                "accidents_total": a,
                "open_complaints": cm,
                "seat_gap_total": sg,
            },
        }
    except Exception as exc:
        log.error("[rafed_kpis] error: %s", exc)
        return {"ok": False, "error": str(exc)}


# --- 3. rafed_schools -------------------------------------------------------
async def handle_rafed_schools(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("search"):
        conds.append(f"(school_name ILIEF ${idx} OR ministerial_number ILIKE ${idx})".replace("ILIEF", "ILIKE"))
        params.append(f"%{args['search']}%")
        idx += 1
    if args.get("sector_id"):
        conds.append(f"sector_id = ${idx}")
        params.append(args["sector_id"])
        idx += 1
    if args.get("administration_id"):
        conds.append(f"administration_id = ${idx}")
        params.append(args["administration_id"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT school_id, ministerial_number, school_name, sector_name_ar, "
        f"administration_name_ar, office_name_ar, gender, education_type, "
        f"allocated_seats, x, y, contract_id "
        f"FROM {SCHEMA}.dim_school{where} "
        f"ORDER BY school_name LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "schools": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 4. rafed_vehicles ------------------------------------------------------
async def handle_rafed_vehicles(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("search"):
        conds.append(f"(plate_ar ILIKE ${idx} OR plate_numbers ILIKE ${idx} OR vehicle_id ILIKE ${idx})")
        params.append(f"%{args['search']}%")
        idx += 1
    if args.get("operator_id"):
        conds.append(f"operator_id = ${idx}")
        params.append(args["operator_id"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("has_gps") is not None:
        conds.append(f"has_gps = ${idx}")
        params.append(args["has_gps"])
        idx += 1
    if args.get("is_special_needs") is not None:
        conds.append(f"is_special_needs = ${idx}")
        params.append(args["is_special_needs"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT vehicle_id, plate_ar, plate_numbers, plate_letters, "
        f"brand_name_ar, model_name_ar, year_model, capacity_official, "
        f"capacity_operational, has_gps, is_gps_connected, has_driver, "
        f"contract_id, operator_id, is_special_needs, special_needs_seats, "
        f"license_expiration_date, periodic_examination_expiration_date, "
        f"insurance_expiration_date, operation_card_expiration_date, is_backup "
        f"FROM {SCHEMA}.dim_vehicle{where} "
        f"ORDER BY plate_ar LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "vehicles": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 5. rafed_drivers -------------------------------------------------------
async def handle_rafed_drivers(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("search"):
        conds.append(f"(driver_name ILIKE ${idx} OR driver_id ILIKE ${idx})")
        params.append(f"%{args['search']}%")
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("is_saudi") is not None:
        conds.append(f"is_saudi = ${idx}")
        params.append(args["is_saudi"])
        idx += 1
    if args.get("is_trained") is not None:
        conds.append(f"is_trained = ${idx}")
        params.append(args["is_trained"])
        idx += 1
    if args.get("compliance_status"):
        conds.append(f"compliance_status = ${idx}")
        params.append(args["compliance_status"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT driver_id, driver_name, nationality_name_ar, is_saudi, "
        f"license_name, license_expiry_date, is_trained, is_first_aid, "
        f"has_criminal_record, traffic_points, compliance_status, age, "
        f"contract_id "
        f"FROM {SCHEMA}.dim_driver{where} "
        f"ORDER BY driver_name LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "drivers": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 6. rafed_accidents -----------------------------------------------------
async def handle_rafed_accidents(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("date_from"):
        conds.append(f"accident_date >= ${idx}")
        params.append(args["date_from"])
        idx += 1
    if args.get("date_to"):
        conds.append(f"accident_date <= ${idx}")
        params.append(args["date_to"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("sector_id"):
        conds.append(f"sector_id = ${idx}")
        params.append(args["sector_id"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT accident_id, accident_date, school_name, accident_type, "
        f"accident_reason, accident_location, operator_name, plate_display, "
        f"injured_students, injured_to_hospital, dead_students, "
        f"driver_injured, driver_dead, status, service_type, "
        f"driver_name, driver_nationality, driver_age, "
        f"has_first_aid, has_fire_extinguisher, has_emergency_exits, "
        f"description, actions_taken, recommendations "
        f"FROM {SCHEMA}.fact_ins_accident{where} "
        f"ORDER BY accident_date DESC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "accidents": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 7. rafed_inspections ---------------------------------------------------
async def handle_rafed_inspections(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("date_from"):
        conds.append(f"inspection_date >= ${idx}")
        params.append(args["date_from"])
        idx += 1
    if args.get("date_to"):
        conds.append(f"inspection_date <= ${idx}")
        params.append(args["date_to"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("school_id"):
        conds.append(f"school_id = ${idx}")
        params.append(args["school_id"])
        idx += 1
    if args.get("inspector_id"):
        conds.append(f"inspector_id = ${idx}")
        params.append(args["inspector_id"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT w.workorder_id, w.school_name, w.inspector_name, "
        f"w.inspection_date, w.score, w.status, w.status_label_ar, "
        f"w.visit_type, w.bus_count, w.ministry_number, "
        f"w.sector_id, w.administration_id "
        f"FROM {SCHEMA}.ins_workorders w{where} "
        f"ORDER BY w.inspection_date DESC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        result: Dict[str, Any] = {"ok": True, "inspections": rows, "count": len(rows), "summary": summary}

        if args.get("include_answers") and rows:
            wo_ids = [str(r.get("workorder_id")) for r in rows[:5]]
            if wo_ids:
                placeholders = ",".join(f"${i+1}" for i in range(len(wo_ids)))
                ans_sql = (
                    f"SELECT workorder_id, question_text, answer_text, "
                    f"category_name, inside, is_solved, fix_type, fix_description "
                    f"FROM {SCHEMA}.fact_inspection_answer "
                    f"WHERE workorder_id IN ({placeholders}) "
                    f"LIMIT 50"
                )
                answers = await rafed_db.execute_query(ans_sql, tuple(wo_ids))
                result["answers"] = answers
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 8. rafed_compliance ----------------------------------------------------
async def handle_rafed_compliance(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    entity = args.get("entity_type", "all")
    days = int(args.get("expiring_within_days", 30))
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    where = _where(conds)
    result: Dict[str, Any] = {"ok": True}

    try:
        if entity in ("drivers", "all"):
            sql = (
                f"SELECT driver_id, driver_name, license_expiry_date, "
                f"traffic_points, compliance_status, license_name, "
                f"is_trained, is_first_aid "
                f"FROM {SCHEMA}.dim_driver{where} "
                f"ORDER BY license_expiry_date NULLS LAST LIMIT 50"
            )
            result["drivers"] = await rafed_db.execute_query(sql, tuple(params) if params else None)

        if entity in ("vehicles", "all"):
            sql = (
                f"SELECT vehicle_id, plate_ar, "
                f"license_expiration_date, "
                f"periodic_examination_expiration_date, "
                f"insurance_expiration_date, "
                f"operation_card_expiration_date, "
                f"is_gps_connected, has_gps "
                f"FROM {SCHEMA}.dim_vehicle{where} "
                f"ORDER BY license_expiration_date NULLS LAST LIMIT 50"
            )
            result["vehicles"] = await rafed_db.execute_query(sql, tuple(params) if params else None)

        if entity in ("contracts", "all"):
            sql = (
                f"SELECT contract_id, contract_number, operator_name, "
                f"active_contract, start_date, end_date, "
                f"total_seats_allocated, students_total "
                f"FROM {SCHEMA}.dim_contract{where} "
                f"ORDER BY end_date NULLS LAST LIMIT 50"
            )
            result["contracts"] = await rafed_db.execute_query(sql, tuple(params) if params else None)

        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 9. rafed_seat_gaps -----------------------------------------------------
async def handle_rafed_seat_gaps(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("school_id"):
        conds.append(f"school_id = ${idx}")
        params.append(args["school_id"])
        idx += 1
    if args.get("only_gaps", True):
        conds.append("gap < 0")
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT school_id, school_name, contract_number, "
        f"allocated_seats, actual_seats, gap, "
        f"ROUND(gap_pct, 2) AS gap_pct "
        f"FROM {SCHEMA}.mv_school_seat_gap{where} "
        f"ORDER BY gap ASC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "seat_gaps": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 10. rafed_routes -------------------------------------------------------
async def handle_rafed_routes(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("school_id"):
        conds.append(f"school_code = ${idx}")
        params.append(args["school_id"])
        idx += 1
    if args.get("vehicle_id"):
        conds.append(f"vehicle_id = ${idx}")
        params.append(args["vehicle_id"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT contract_number, school_code, school_name, "
        f"vehicle_id, plate_display, round_no, students_planned, "
        f"operation_number "
        f"FROM {SCHEMA}.fact_plan_route{where} "
        f"ORDER BY school_code, round_no LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "routes": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 11. rafed_complaints ---------------------------------------------------
async def handle_rafed_complaints(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("date_from"):
        conds.append(f"complaint_date >= ${idx}")
        params.append(args["date_from"])
        idx += 1
    if args.get("date_to"):
        conds.append(f"complaint_date <= ${idx}")
        params.append(args["date_to"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("category"):
        conds.append(f"category = ${idx}")
        params.append(args["category"])
        idx += 1
    if args.get("status"):
        conds.append(f"status = ${idx}")
        params.append(args["status"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT complaint_id, complaint_date, channel, category, "
        f"status, severity, summary, resolved_at, source_system, "
        f"contract_number "
        f"FROM {SCHEMA}.fact_complaint{where} "
        f"ORDER BY complaint_date DESC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "complaints": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 12. rafed_safety_checks ------------------------------------------------
async def handle_rafed_safety_checks(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("date_from"):
        conds.append(f"check_date >= ${idx}")
        params.append(args["date_from"])
        idx += 1
    if args.get("date_to"):
        conds.append(f"check_date <= ${idx}")
        params.append(args["date_to"])
        idx += 1
    if args.get("contract_id"):
        conds.append(f"contract_number = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("check_type"):
        conds.append(f"check_type = ${idx}")
        params.append(args["check_type"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT id, check_type, check_date, driver_name, "
        f"contract_number, ministerial_number, "
        f"q1_answer, q2_answer, q3_answer, q4_answer, q5_answer, "
        f"q6_answer, q7_answer, q8_answer, q9_answer, q10_answer, "
        f"q11_answer, q12_answer, q13_answer "
        f"FROM {SCHEMA}.fact_safety_check{where} "
        f"ORDER BY check_date DESC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "safety_checks": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 13. rafed_school_visits ------------------------------------------------
async def handle_rafed_school_visits(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("date_from"):
        conds.append(f"DATE(event_time) >= ${idx}")
        params.append(args["date_from"])
        idx += 1
    if args.get("date_to"):
        conds.append(f"DATE(event_time) <= ${idx}")
        params.append(args["date_to"])
        idx += 1
    if args.get("school_code"):
        conds.append(f"school_code = ${idx}")
        params.append(args["school_code"])
        idx += 1
    if args.get("event_type"):
        conds.append(f"event_type = ${idx}")
        params.append(args["event_type"])
        idx += 1
    lim = _limit(args, default=20, maximum=50)
    where = _where(conds)
    sql = (
        f"SELECT school_code, school_name, event_type, event_time, "
        f"distance_m, plate_letters, plate_numbers, latitude, longitude "
        f"FROM {SCHEMA}.fact_school_visit{where} "
        f"ORDER BY event_time DESC LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "visits": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 14. rafed_assignments --------------------------------------------------
async def handle_rafed_assignments(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("school_id"):
        conds.append(f"school_id = ${idx}")
        params.append(args["school_id"])
        idx += 1
    if args.get("vehicle_id"):
        conds.append(f"vehicle_id = ${idx}")
        params.append(args["vehicle_id"])
        idx += 1
    if args.get("driver_id"):
        conds.append(f"driver_id = ${idx}")
        params.append(args["driver_id"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT student_id, school_id, school_code, vehicle_id, "
        f"driver_id, contract_id, contract_number, rafed_tier, "
        f"rafed_category, stage, gender_label_ar, distance_km, "
        f"duration_sec "
        f"FROM {SCHEMA}.fact_assignment{where} "
        f"ORDER BY school_code LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "assignments": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 15. rafed_operators ----------------------------------------------------
async def handle_rafed_operators(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("search"):
        conds.append(f"operator_name ILIKE ${idx}")
        params.append(f"%{args['search']}%")
        idx += 1
    if args.get("is_sub") is not None:
        conds.append(f"is_sub = ${idx}")
        params.append(args["is_sub"])
        idx += 1
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT operator_id, operator_name, hafelat_cr, is_sub, "
        f"category_id, category_name_ar "
        f"FROM {SCHEMA}.dim_operator{where} "
        f"ORDER BY operator_name LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "operators": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 16. rafed_contracts ----------------------------------------------------
async def handle_rafed_contracts(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    conds: List[str] = []
    params: List[Any] = []
    idx = 1
    if args.get("contract_id"):
        conds.append(f"contract_id = ${idx}")
        params.append(args["contract_id"])
        idx += 1
    if args.get("operator_id"):
        conds.append(f"operator_id = ${idx}")
        params.append(args["operator_id"])
        idx += 1
    if args.get("sector_id"):
        conds.append(f"sector_id = ${idx}")
        params.append(args["sector_id"])
        idx += 1
    if args.get("active_only", True):
        conds.append("active_contract = true")
    lim = _limit(args)
    where = _where(conds)
    sql = (
        f"SELECT contract_id, contract_number, operator_name, "
        f"sector_name_ar, administration_name_ar, office_name_ar, "
        f"gender, education_type, education_level, students_total, "
        f"total_seats_allocated, total_seats_reversed, start_date, "
        f"end_date, hijri_start_date, hijri_end_date, active_contract, "
        f"amount, region_name_ar, erp_contract_number "
        f"FROM {SCHEMA}.dim_contract{where} "
        f"ORDER BY contract_number LIMIT {lim}"
    )
    try:
        rows = await rafed_db.execute_query(sql, tuple(params) if params else None)
        summary = _compact_summary(rows)
        await _auto_speak(summary)
        return {"ok": True, "contracts": rows, "count": len(rows), "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --- 17. show_visual -------------------------------------------------------
async def handle_show_visual(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from . import dashboard_server
    layout = {
        "title": args.get("title", ""),
        "subtitle": args.get("subtitle", ""),
        "columns": int(args.get("columns", 2)),
        "components": args.get("components", []),
    }
    dashboard_server.push_layout_sync(layout)
    log.info("[show_visual] pushed layout: %s (%d components)",
             layout["title"], len(layout["components"]))
    return {"ok": True, "message": "Dashboard updated"}


# --- 18. dashboard_init ----------------------------------------------------
async def handle_dashboard_init(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from . import dashboard_server
    title = args.get("title", "")
    subtitle = args.get("subtitle", "")
    columns = int(args.get("columns", 2))
    dashboard_server.push_init_sync(title, subtitle, columns)
    log.info("[dashboard_init] init: %s (cols=%d)", title, columns)
    return {"ok": True, "message": "Dashboard initialized"}


# --- 19. dashboard_add -----------------------------------------------------
async def handle_dashboard_add(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from . import dashboard_server
    component = args.get("component", {})
    if not component or not isinstance(component, dict):
        return {"ok": False, "error": "Missing or invalid 'component' parameter"}
    dashboard_server.push_add_component_sync(component)
    log.info("[dashboard_add] added: %s", component.get("type", "?"))
    return {"ok": True, "message": f"Added {component.get('type', 'component')}"}


# --- 20. dashboard_clear ---------------------------------------------------
async def handle_dashboard_clear(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from . import dashboard_server
    dashboard_server.push_clear_sync()
    log.info("[dashboard_clear] screen cleared")
    return {"ok": True, "message": "Dashboard cleared"}


# ---------------------------------------------------------------------------
# Registry — maps tool name → (definition, handler)
# ---------------------------------------------------------------------------
HANDLERS = {
    "rafed_query": handle_rafed_query,
    "rafed_kpis": handle_rafed_kpis,
    "rafed_schools": handle_rafed_schools,
    "rafed_vehicles": handle_rafed_vehicles,
    "rafed_drivers": handle_rafed_drivers,
    "rafed_accidents": handle_rafed_accidents,
    "rafed_inspections": handle_rafed_inspections,
    "rafed_compliance": handle_rafed_compliance,
    "rafed_seat_gaps": handle_rafed_seat_gaps,
    "rafed_routes": handle_rafed_routes,
    "rafed_complaints": handle_rafed_complaints,
    "rafed_safety_checks": handle_rafed_safety_checks,
    "rafed_school_visits": handle_rafed_school_visits,
    "rafed_assignments": handle_rafed_assignments,
    "rafed_operators": handle_rafed_operators,
    "rafed_contracts": handle_rafed_contracts,
    "show_visual": handle_show_visual,
    "dashboard_init": handle_dashboard_init,
    "dashboard_add": handle_dashboard_add,
    "dashboard_clear": handle_dashboard_clear,
}
