#!/usr/bin/env python3
"""One-time script: updates Haseef's cloud system prompt to include Rafed data tools
and removes old face recognition tool references."""
import asyncio
import os
import re

from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv()

NEW_RAFED_SECTION = """
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
    prompt = cfg.get("system_prompt", "")

    # Remove face recognition sections
    s = prompt.find("=== HOW TO HANDLE PEOPLE")
    e = prompt.find("=== HOW YOU RECEIVE TASKS ===")
    if s > 0 and e > s:
        prompt = prompt[:s] + prompt[e:]

    # Remove face tool lines
    for ft in ["enroll_face", "forget_face", "list_known_faces",
               "who_is_visible", "follow_face", "stop_following"]:
        prompt = re.sub(
            r"\n- " + ft + r".*?(?=\n- |\n\n===)",
            "",
            prompt,
            flags=re.DOTALL,
        )

    # Remove face-related examples
    for pattern in [
        r'Task: "Remember me as Husam".*?\n.*?\n.*?\n',
        r'Task: "Who is in front of you\?".*?\n.*?\n.*?\n',
        r'Task: "Follow me".*?\n.*?\n.*?\n',
        r'Task: "Stop following me".*?\n.*?\n.*?\n',
        r'Task: "Forget me.*?\n.*?\n.*?\n',
    ]:
        prompt = re.sub(pattern, "", prompt, flags=re.DOTALL)

    # Insert Rafed section before HOW YOU RECEIVE TASKS
    idx = prompt.find("=== HOW YOU RECEIVE TASKS ===")
    if idx > 0:
        prompt = prompt[:idx] + NEW_RAFED_SECTION + "\n" + prompt[idx:]
    else:
        prompt += "\n" + NEW_RAFED_SECTION

    cfg["system_prompt"] = prompt
    cfg["max_tokens"] = 4096

    result = await sdk.haseef.update(hid, {"configJson": cfg})
    new_cfg = result.get("configJson", {})
    print("OK - prompt length:", len(new_cfg.get("system_prompt", "")))
    print("max_tokens:", new_cfg.get("max_tokens"))


if __name__ == "__main__":
    asyncio.run(main())
