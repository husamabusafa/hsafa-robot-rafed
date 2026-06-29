#!/usr/bin/env python3
"""Fix Haseef prompt: remove duplicate Rafed sections, add single clean one."""
import asyncio
import os
import re

from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv()

RAFED = """
=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===
You have access to a PostgreSQL database with 13.5 million rows of school
transport data. ALWAYS call the appropriate tool, then call say_this() to
deliver the answer. The user CANNOT hear your thoughts.

DATA TOOLS:
- rafed_query(sql, description?): Run any SELECT SQL. Tables in v_current schema.
  Use _ar columns for Arabic. LIMIT 100 max. Only SELECT.
- rafed_kpis(contract_id?, operator_id?, sector_id?): KPI dashboard.
- rafed_schools(search?, sector_id?, contract_id?, limit?): Search schools.
- rafed_vehicles(search?, has_gps?, expiring_within_days?, limit?): Search buses.
- rafed_drivers(search?, is_saudi?, compliance_status?, limit?): Search drivers.
- rafed_accidents(date_from?, date_to?, sector_id?, limit?): Accident reports.
- rafed_inspections(date_from?, status?, include_answers?, limit?): Inspections.
- rafed_compliance(entity_type?, expiring_within_days?): Compliance status.
- rafed_seat_gaps(contract_id?, only_gaps?, limit?): Seat gap analysis.
- rafed_routes(contract_id?, school_id?, limit?): Planned routes.
- rafed_complaints(date_from?, category?, status?, limit?): Complaints.
- rafed_safety_checks(date_from?, check_type?, limit?): Safety checks.
- rafed_school_visits(date_from?, school_code?, limit?): Bus arrivals/departures.
- rafed_assignments(contract_id?, school_id?, limit?): Student assignments.
- rafed_operators(search?, limit?): Search operators.
- rafed_contracts(operator_id?, active_only?, limit?): Contract details.

ANSWER PROTOCOL FOR DATA QUESTIONS:
1. Call the right tool to get data.
2. The tool returns a "summary" field with a pre-formatted Arabic text.
3. Call say_this(text=summary) to speak it. You may rephrase it naturally.
4. NEVER skip step 3. The user is waiting.

EXAMPLES:
Task: "How many schools?" -> call rafed_kpis(), then say_this(text=summary)
Task: "Buses without GPS?" -> call rafed_vehicles(has_gps=false, limit=1), then say_this(text=summary)
Task: "Recent accidents" -> call rafed_accidents(limit=5), then say_this(text=summary)

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

    count = p.count("=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===")
    print(f"Rafed sections before: {count}")

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

    # Insert single clean Rafed section
    idx = p.find("=== HOW YOU RECEIVE TASKS ===")
    if idx > 0:
        p = p[:idx] + RAFED + p[idx:]
    else:
        p += RAFED

    # Clean up excessive blank lines
    p = re.sub(r"\n{4,}", "\n\n\n", p)

    cfg["system_prompt"] = p
    cfg["max_tokens"] = 4096
    result = await sdk.haseef.update(hid, {"configJson": cfg})
    new_p = result.get("configJson", {}).get("system_prompt", "")
    print(f"Rafed sections after: {new_p.count('=== RAFED SCHOOL TRANSPORT DATA WAREHOUSE ===')}")
    print(f"Prompt length: {len(new_p)}")


if __name__ == "__main__":
    asyncio.run(main())
