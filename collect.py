#!/usr/bin/env python3
import os
import requests
import pandas as pd
from datetime import datetime, time, timezone

# --- Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
PROJECT_ID = "6fxHrQ58f8jFXp24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    exit(1)

# --- Build ISO since/until for "today" in UTC (adjust if you want local-day semantics) ---
today_utc = datetime.now(timezone.utc).date()
since = datetime.combine(today_utc, time.min, tzinfo=timezone.utc).isoformat()
until = datetime.combine(today_utc, time.max, tzinfo=timezone.utc).isoformat()

# --- Endpoint using /api/v1 prefix per deprecation message ---
URL = "https://api.todoist.com/api/v1/completed/get_all"
headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}

limit = 200
offset = 0
completed_items = []

print(f"Fetching completed items for {today_utc.isoformat()} (UTC) from {URL} ...")

while True:
    params = {"since": since, "until": until, "limit": limit, "offset": offset}
    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error when calling Todoist API: {e}")
        exit(1)

    # Surface deprecation / migration errors clearly
    if resp.status_code == 410:
        try:
            err = resp.json()
            extra = err.get("error_extra", {})
            retry_after = extra.get("retry_after")
        except Exception:
            retry_after = None
        msg = "❌ Todoist API returned 410 API_DEPRECATED. The endpoint/version is removed."
        if retry_after:
            msg += f" Server suggests retry_after={retry_after} seconds."
        print(msg)
        exit(1)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error from Todoist API: {e} (status {resp.status_code})")
        print("Response body:", resp.text)
        exit(1)

    data = resp.json()
    items = data.get("items", [])
    if not items:
        break

    completed_items.extend(items)
    offset += len(items)
    if len(items) < limit:
        break

print(f"✅ Retrieved {len(completed_items)} completed items (raw) for {today_utc.isoformat()}")

# --- Load or create CSV ---
csv_path = os.path.join(BASE_DIR, "food_record.csv")
try:
    food_record = pd.read_csv(csv_path)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

today_str = today_utc.isoformat()
new_entries = []

# --- Filter by project_id and dedupe ---
for item in completed_items:
    if str(item.get("project_id", "")) != str(PROJECT_ID):
        continue
    food_name = item.get("content", "").strip()
    if not food_name:
        continue
    is_dup = ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any()
    if not is_dup:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")

# --- Save results ---
if new_entries:
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Successfully updated {csv_path}")
else:
    print("ℹ No new items found to log for today.")
