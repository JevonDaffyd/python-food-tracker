#!/usr/bin/env python3
import os
import requests
import pandas as pd
from datetime import datetime, timedelta

TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    exit(1)

# Sync API endpoint for completed items
URL = "https://api.todoist.com/sync/v9/completed/get_all"
headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}

# Build since/until for today in ISO format
today = datetime.utcnow().date()
since = datetime.combine(today, datetime.min.time()).isoformat() + "Z"
until = datetime.combine(today, datetime.max.time()).isoformat() + "Z"

params = {"since": since, "until": until, "limit": 200}

try:
    resp = requests.get(URL, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    completed_items = data.get("items", [])
    print(f"✅ Retrieved {len(completed_items)} completed items for {today.isoformat()}")
except requests.exceptions.RequestException as e:
    print(f"❌ Sync API Error: {e}")
    exit(1)

# Continue with your CSV logic using completed_items; each item typically has 'content'
csv_path = os.path.join(BASE_DIR, "food_record.csv")
try:
    food_record = pd.read_csv(csv_path)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

today_str = today.isoformat()
new_entries = []
for item in completed_items:
    food_name = item.get("content", "").strip()
    if not food_name:
        continue
    is_dup = ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any()
    if not is_dup:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")

if new_entries:
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Successfully updated {csv_path}")
else:
    print("ℹ No new items found to log for today.")
