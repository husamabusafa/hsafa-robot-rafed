"""rafed_db.py — Async PostgreSQL connection pool for the Rafed data warehouse.

Provides a singleton pool and a query executor with safety guards:
  - read-only enforcement (rejects destructive SQL)
  - row limit (LIMIT 100 max)
  - query timeout (5 seconds)
  - JSON-serializable results
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

log = logging.getLogger("rafed_db")

DEFAULT_DSN = os.getenv("RAFED_DB_URL", "postgresql://husamabusafa@localhost:5432/rafed")
MAX_ROWS = 100
QUERY_TIMEOUT_S = 5.0

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|VACUUM)\b",
    re.IGNORECASE,
)

_pool: Optional[asyncpg.Pool] = None


async def init_pool(dsn: str = DEFAULT_DSN, min_size: int = 1, max_size: int = 3) -> asyncpg.Pool:
    """Initialise the global connection pool. Call once at startup."""
    global _pool
    if _pool is not None:
        return _pool
    log.info("[rafed_db] Creating pool → %s", _redact_dsn(dsn))
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=QUERY_TIMEOUT_S,
    )
    log.info("[rafed_db] Pool ready (min=%d max=%d)", min_size, max_size)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("[rafed_db] Pool closed.")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("rafed_db pool not initialised — call init_pool() first")
    return _pool


def _redact_dsn(dsn: str) -> str:
    return re.sub(r"://([^:]+):([^@]+)@", r":/\1:***@", dsn)


def _is_safe_sql(sql: str) -> bool:
    return not _FORBIDDEN.search(sql.strip())


def _ensure_limit(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    if re.search(r"\bLIMIT\b", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped} LIMIT {MAX_ROWS}"


def _row_to_dict(record: asyncpg.Record) -> Dict[str, Any]:
    return {k: _coerce(v) for k, v in record.items()}


def _coerce(v: Any) -> Any:
    import uuid
    from decimal import Decimal
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return None
    return v


async def execute_query(
    sql: str,
    params: Optional[Tuple] = None,
    *,
    row_limit: int = MAX_ROWS,
) -> List[Dict[str, Any]]:
    """Execute a read-only SQL query and return rows as list of dicts."""
    if not _is_safe_sql(sql):
        raise ValueError("Rejected: query contains forbidden (non-read-only) keywords")

    pool = get_pool()
    safe_sql = _ensure_limit(sql)
    if row_limit > MAX_ROWS:
        row_limit = MAX_ROWS

    async with pool.acquire() as conn:
        rows = await conn.fetch(safe_sql, *(params or ()))
        results = [_row_to_dict(r) for r in rows[:row_limit]]
        log.info("[rafed_db] query OK → %d rows | %.80s", len(results), safe_sql)
        return results


async def execute_one(
    sql: str,
    params: Optional[Tuple] = None,
) -> Optional[Dict[str, Any]]:
    """Execute a query expected to return a single row."""
    rows = await execute_query(sql, params, row_limit=1)
    return rows[0] if rows else None


async def execute_scalar(
    sql: str,
    params: Optional[Tuple] = None,
) -> Any:
    """Execute a query expected to return a single scalar value."""
    row = await execute_one(sql, params)
    if row:
        return next(iter(row.values()))
    return None


# ---------------------------------------------------------------------------
# Schema metadata — compact description for Haseef prompt injection
# ---------------------------------------------------------------------------
SCHEMA_DESCRIPTION = """\
Rafed School Transport Data Warehouse (schema: v_current)

DIMENSION TABLES:
- dim_school(school_id PK, ministerial_number, school_name, contract_id FK, sector_id, sector_name_ar, administration_id, administration_name_ar, office_id, office_name_ar, gender, education_type, allocated_seats, x, y, academic_year)
- dim_noor_school(school_code PK, school_name, contract_number, rafed_school_id, sector_name, office_name, administration_name, gender, education_type, education_level, allocated_seats, assigned_students, student_count, x, y, region_name_ar)
- dim_vehicle(vehicle_id PK, plate_ar, contract_id FK, operator_id FK, is_sub_operator, brand_name_ar, model_name_ar, year_model, capacity_official, capacity_operational, has_gps, has_driver, device_imei, device_sim, plate_letters, plate_numbers, license_expiration_date, periodic_examination_expiration_date, insurance_type_id, insurance_expiration_date, operational_number, is_gps_connected, is_special_needs, special_needs_type, special_needs_seats, is_backup, operation_card_expiration_date)
- dim_driver(driver_id PK, driver_name, driver_nid_hash, iqama, nationality_id, nationality_name_ar, license_id, license_name, is_saudi, is_first_aid, is_trained, has_criminal_record, contract_id FK, license_expiry_date, traffic_points, compliance_status, birth_date, hijri_birth_date, age)
- dim_escort(escort_id PK, name, operator_id FK, is_saudi, nid_number, nationality_id, age, phone_number, contract_id FK, vehicle_id FK, is_active)
- dim_operator(operator_id PK, operator_name, hafelat_cr, is_sub, category_id, category_name_ar)
- dim_contract(contract_id PK, contract_number, operator_id FK, operator_name, sub_operator_id, is_main_operator, sector_id, sector_name_ar, administration_id, administration_name_ar, office_id, office_name_ar, gender, education_type, education_level, students_total, allocated_seats_male, allocated_seats_female, total_seats_allocated, total_seats_reversed, start_date, end_date, hijri_start_date, hijri_end_date, active_contract, academic_year, amount, region_name_ar, erp_contract_number)
- dim_inspector(inspector_id PK, inspector_name, sector_id, administration_id, is_supervisor, is_admin)
- dim_geofence(geofence_id PK, name_ar, school_code, school_id, contract_id, center_x, center_y, radius_m, geofence_type, source_system)
- dim_domain(domain_name PK, code, label_ar, label_en, parent_code)
- dim_calendar(calendar_date PK, hijri_date, is_school_day, is_holiday, holiday_name_ar, term, academic_year)
- dim_weather_daily(weather_date PK, region_id, region_name_ar, temp_max_c, temp_min_c, precipitation_mm, wind_max_kmh, visibility_km, weather_code, conditions_ar)

FACT TABLES:
- fact_school_visit(id PK, device_imei, school_code, school_name, event_type, event_time, latitude, longitude, distance_m, plate_letters, plate_numbers, education_level, school_gender) — 5.9M rows, bus arrivals/departures
- fact_inspection_answer(id PK, answer_id, workorder_detail_id, workorder_id, question_id, answer_text, question_text, category_name, inside, is_ods_plan, is_solved, solved_date, is_esclated, violation_form_8, exclude_vehicle, exclude_report8, need_processing, fix_type, fixed_at, fix_description, contractor_note, supervisor_note, status_id, contract_id, bus_id) — 4.4M rows
- fact_ins_violence(violence_id PK, violence_type_id, violence_category_id, violence_date, status_id, bus_serial, bus_plate, contract_id, contractor_id, sector_id, administration_id) — 2M rows
- fact_assignment(assignment_id PK, student_id, student_name_hash, school_id, vehicle_id, contract_id, driver_id, academic_year, rafed_tier, rafed_category, stage, gender, home_x, home_y, distance_km, duration_sec, school_code, contract_number, student_nid_hash, gender_label_ar) — 749K rows
- fact_inspection_detail(detail_id PK, workorder_id, bus_id, contract_id, contractor_id, status_id, status_label_ar, inspection_status_id, plate_number, is_ods_plan, is_excluded, fail_reason_id, answer_count, pass_answer_count, violation_answer_count, compliance_pct, vehicle_id, plate_display) — 156K rows
- ins_workorders(workorder_id PK, school_id, contract_id, status, inspection_date, score, ministry_number, school_name, status_label_ar, inspector_id, sector_id, administration_id, visit_type, scheduled_date, actual_start, actual_end, bus_count, inspector_name) — 61K rows
- fact_survey_answer(answer_id PK, submission_id, survey_id, submission_uuid, question_code, question_text_ar, category_name_ar, answer_code, answer_label_ar, school_id, school_name, education_zone_code, driver_id, driver_name, status, latitude, longitude, submitted_at, created_at) — 54K rows
- fact_safety_check(id PK, check_type, check_date, nid_number, driver_name, contract_number, ministerial_number, q1_answer..q13_answer, q1_photo_url..q12_photo_url, q1_answer_ev..q3_answer_ev, q3_photo_url_ev) — 46K rows
- fact_vehicle_kpi(vehicle_id PK, as_of_date, riders, capacity_operational, utilization_pct, age_years, violations_count, rule_1_violation, rule_2_violation, rule_3_violation, rule_4_violation, rule_7_violation, contract_id) — 25K rows
- fact_plan_route(contract_number, contract_id, school_code, school_name, vehicle_id, plate_display, round_no, students_planned, operation_number, resolved_vehicle_id) — 22K rows
- fact_driver_training(id PK, training_date, nid_number, name, phone_number, operator_name, coach_name, sector, offices, place_of_training, has_basic_training, has_advanced_training, status) — 19K rows
- fact_batch_import(id PK, batch_id, batch_type, contract_id, operator_id, sub_operator_id, status, done_count, fail_count, total_count, extra) — 18K rows
- fact_seat_gap(school_id, contract_id, allocated_seats, actual_seats, gap, school_code, contract_number, school_name) — 12K rows
- fact_ins_accident(accident_id PK, contract_id, contract_number, sector_id, administration_id, school_name, accident_date, accident_type, accident_reason, accident_location, operator_name, plate_numbers, plate_display, bus_serial, vehicle_id, injured_students, injured_to_hospital, dead_students, dead_second_party, driver_injured, driver_dead, status, close_case_date, service_type, educational_level, disability_type, is_reported, total_students, injured_second_party, description, vehicle_type, vehicle_company, vehicle_model, driver_name, driver_nationality, driver_age, driver_license_type, license_expiration, has_first_aid, has_fire_extinguisher, has_emergency_exits, accident_coordinates, actions_taken, recommendations) — 561 rows
- fact_safety_accident(id PK, report_type, report_date, nid_number, driver_name, contract_number, ministerial_number, has_accident, supervisor_notified, accident_datetime, students_in_bus, students_injured, photo_urls, photos_count, accident_latitude, accident_longitude) — 201 rows
- fact_audit_violation(violation_id PK, period_id, report_id, contract_id, operator_id, code, value) — 441 rows
- fact_complaint(complaint_id PK, contract_id, contract_number, complaint_date, channel, category, status, severity, summary, resolved_at, source_system) — 621 rows
- fact_contract_readiness(contract_id PK, as_of_date, total_buses, total_drivers, ready_buses, with_gps_buses, students_contract, students_transferred, transfer_pct, avg_bus_target_pct, avg_ready_pct, pct_exempt_served, pct_paid_served, priority_segments) — 80 rows
- fact_daily_snapshot(snapshot_date PK, total_students, students_with_vehicle, students_without_vehicle, total_vehicles, vehicles_with_gps, vehicles_with_license_expiring_30d, vehicles_with_inspection_expiring_30d, vehicles_with_insurance_expiring_30d, total_drivers, total_escorts, total_schools, total_contracts, morning_checks_today, evening_checks_today, safety_accidents_today, inspection_visits_today, inspection_pass_rate, inspection_fail_rate, violence_incidents_today, fact_ins_accidents_today) — 1 row
- fact_fuel(fuel_id PK, vehicle_id, contract_id, fill_date, liters, amount_sar, odometer_km, provider_name, card_number_hash, source_system)
- fact_geofence_event(event_id PK, geofence_id, vehicle_id, contract_id, event_time, event_type, lat, lng, speed_kmh, source_system)
- fact_ridership_daily(student_id, ridership_date, school_code, contract_id, vehicle_id, boarded, no_show, check_in_method, trip_id, source_system)
- fact_trip_daily(trip_date, contract_id, operator_id, vehicle_id, trip_count, distance_km, on_time_pct, avg_delay_min, source_system)

MATERIALIZED VIEWS:
- mv_plan_summary(contract_id, contract_number, operator_id, operator_name, sector_id, sector_name_ar, totalbus, ready, with_gps, ready_pct, bus_target_pct, students_total, students_transferred, transfer_pct)
- mv_school_plan(school_code, school_name, contract_number, contract_id, bus_count, students_planned)
- mv_school_seat_gap(school_id, school_name, contract_id, contract_number, allocated_seats, actual_seats, gap, gap_pct, school_code)

KEY RELATIONSHIPS:
- dim_contract.contract_id → fact_assignment, fact_ins_accident, fact_inspection_detail, fact_complaint, fact_seat_gap, fact_plan_route, fact_vehicle_kpi, fact_contract_readiness, dim_vehicle, dim_driver
- dim_school.school_id → fact_assignment, fact_seat_gap, ins_workorders
- dim_vehicle.vehicle_id → fact_assignment, fact_vehicle_kpi, fact_plan_route, dim_escort
- dim_driver.driver_id → fact_assignment, fact_safety_check
- dim_operator.operator_id → dim_vehicle, dim_operator
- dim_inspector.inspector_id → ins_workorders
- dim_calendar.calendar_date → all fact tables (via date columns)

NOTES:
- Columns ending with _ar contain Arabic text (prefer these when answering in Arabic)
- Student/driver IDs are hashed (student_name_hash, driver_nid_hash) — never expose raw hashes
- All queries must use schema prefix v_current. (e.g., v_current.dim_school)
- GPS coordinates: x = longitude, y = latitude
"""
