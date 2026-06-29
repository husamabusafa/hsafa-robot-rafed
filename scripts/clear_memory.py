#!/usr/bin/env python3
"""clear_memory.py — Delete all semantic memory for a Haseef robot.

Usage:
    python scripts/clear_memory.py

Reads HSAFA_CORE_URL, HSAFA_CORE_KEY, and HASEEF_ID from .env.
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

core_url = os.environ.get("HSAFA_CORE_URL", "https://core.hsafa.com")
core_key = os.environ.get("HSAFA_CORE_KEY", "")
haseef_id = os.environ.get("HASEEF_ID", "")

if not core_key or not haseef_id:
    print("Error: HSAFA_CORE_KEY and HASEEF_ID must be set in .env", file=sys.stderr)
    sys.exit(1)


async def main():
    sdk = HsafaSDK(SdkOptions(core_url=core_url, api_key=core_key))

    # List all semantic memories
    memories = await sdk.memory.list(haseef_id)
    if not memories:
        print("No memories found — robot mind is already clean.")
        return

    print(f"Found {len(memories)} memories:")
    for m in memories:
        key = m.get("key", "?")
        val = m.get("value", "")[:80]
        print(f"  - [{key}] {val}")

    # Collect all keys and delete
    keys = [m.get("key") for m in memories if m.get("key")]
    if keys:
        await sdk.memory.delete(haseef_id, keys)
        print(f"\nDeleted {len(keys)} memories. Robot mind is now clean.")
    else:
        print("\nNo keys found to delete.")

    await sdk.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
