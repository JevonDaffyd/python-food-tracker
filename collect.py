#!/usr/bin/env python3
import requests
import os
import pandas as pd
from datetime import datetime, timezone
from todoist_api_python.api import TodoistAPI

# --- 1. Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
# This is your "Public" ID from the URL
ALPHANUMERIC_PROJECT_ID = "6fxHrQ58f8jFXp24" 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    exit(1)

# --- 2. ID Translation (The Fix) ---
api = TodoistAPI(TODOIST_TOKEN)
try:
    project = api.get_project(project_id=ALPHANUMERIC_PROJECT_ID)
    # This 'project.id' will be the NUMERIC string required by the Sync API
    NUMERIC_ID = project.id 
    print(f"✅ Verified Project: {project.name} (Internal ID: {NUMERIC_ID})")
except Exception as e:
    print(f"❌ Could not verify project ID: {e}")
    exit(1)

# --- 3. Fetch Today's Completions (Sync API v9) ---
SYNC_URL = "https://api.todoist.com/sync/v9/completed/get_all"
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
since_str = today_start.strftime('%Y-%m-%dT%H:%M:%SZ')

headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
params = {
    "project_id": NUMERIC_ID,  # We use the translated Numeric ID here
    "since": since_str,
    "limit": 100
}

try:
    response = requests.get(SYNC_URL, headers=headers, params=params)
    response.raise_for_status()
    completed_items = response.json().get("items", [])
    print(f"✓ Found {len(completed_items)} completed items today.")
except requests.exceptions.RequestException as e:
    print(f"❌ Sync API Error: {e}")
    exit(1)

# --- 4. Update CSV ---
today_str = datetime.now().strftime('%Y-%m-%d')
csv_path = os.path.join(BASE_DIR, "food_record.csv")

try:
    food_record = pd.read_csv(csv_path)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

new_entries = []
for item in completed_items:
    food_name = item.get('content', '').strip()
    if food_name and not ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any():
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")

if new_entries:
    food_record = pd.concat([food_record, pd.DataFrame(new_entries)], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Saved {len(new_entries)} new items.")
else:
    print("ℹ No new items to log.")
