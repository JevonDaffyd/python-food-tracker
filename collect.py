#!/usr/bin/env python3
"""
Fetch completed items via the documented Todoist API v1 Sync endpoint,
filter by project_id, and append new entries to food_record.csv.

Relies exclusively on the API v1 Sync endpoint documented at:
https://developer.todoist.com/api/v1/
"""
import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timezone

# --- Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
PROJECT_ID = "6fxHrQ58f8jFXp24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "food_record.csv")

if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    sys.exit(1)

SYNC_URL = "https://api.todoist.com/api/v1/sync"
HEADERS = {"Authorization": f"Bearer {TODOIST_TOKEN}"}

# --- Build sync request (full sync) ---
payload = {
    "sync_token": "*",
    "resource_types": json.dumps(["all"])  # documented format: JSON-encoded array
}

print("Requesting full sync from Todoist API v1...")

try:
    resp = requests.post(SYNC_URL, headers=HEADERS, data=payload, timeout=30)
except requests.exceptions.RequestException as e:
    print(f"❌ Network error calling Sync API: {e}")
    sys.exit(1)

# Surface deprecation clearly if server removed endpoint/version
if resp.status_code == 410:
    try:
        err = resp.json()
        extra = err.get("error_extra", {})
        retry_after = extra.get("retry_after")
        event_id = extra.get("event_id")
    except Exception:
        retry_after = None
        event_id = None
    msg = "❌ Todoist API returned 410 API_DEPRECATED. The endpoint/version is removed."
    if retry_after:
        msg += f" Server suggests retry_after={retry_after}s."
    if event_id:
        msg += f" event_id={event_id}."
    print(msg)
    sys.exit(1)

if resp.status_code != 200:
    print(f"❌ Todoist API returned HTTP {resp.status_code}")
    print("Response body:", resp.text)
    sys.exit(1)

try:
    data = resp.json()
except ValueError:
    print("❌ Failed to parse JSON from Todoist response.")
    sys.exit(1)

# --- Locate completed items in the documented response ---
# The Sync response may include completed-related fields. Check common keys.
completed_items = []

# 1) If the response contains an explicit 'completed_items' array, use it.
if isinstance(data.get("completed_items"), list):
    completed_items = data.get("completed_items", [])

# 2) Some full-sync responses include 'items' and/or 'completed_info'.
#    If 'items' contains completed items (older/newer clients may include a flag),
#    attempt to detect completed entries by presence of 'is_completed' or 'checked' fields.
elif isinstance(data.get("items"), list):
    for it in data.get("items", []):
        # Common patterns: 'is_completed' boolean, 'checked' integer, or 'completed_at' timestamp
        if it.get("is_completed") or it.get("checked") or it.get("completed_at"):
            completed_items.append(it)

# 3) If neither key is present, but completed_info exists, surface a helpful error.
elif data.get("completed_info"):
    print("ℹ Sync returned 'completed_info' but no explicit completed items.")
    print("This account's Sync response includes counts but not item details.")
    print("Response snippet:", json.dumps({"completed_info": data.get("completed_info")})[:1000])
    sys.exit(1)
else:
    print("❌ Sync response did not include completed items or completed_info.")
    print("Response keys:", ", ".join(sorted(data.keys())))
    sys.exit(1)

print(f"✅ Raw completed items found: {len(completed_items)}")

# --- Load or create CSV ---
try:
    food_record = pd.read_csv(CSV_PATH)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

today_str = datetime.now(timezone.utc).date().isoformat()
new_entries = []

# --- Filter by project_id and dedupe ---
for item in completed_items:
    # The documented item fields include 'content' and 'project_id' when present.
    proj = item.get("project_id") or item.get("project") or item.get("project_id_str")
    if proj is None:
        # If project id not present, skip (can't attribute to your project)
        continue
    if str(proj) != str(PROJECT_ID):
        continue

    food_name = item.get("content", "").strip()
    if not food_name:
        continue

    is_dup = ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any()
    if not is_dup:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Queued to log: {food_name}")

# --- Save results ---
if new_entries:
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(CSV_PATH, index=False, encoding="utf-8")
    print(f"✅ Successfully updated {CSV_PATH} with {len(new_entries)} new entries.")
else:
    print("ℹ No new items found to log for today.")
