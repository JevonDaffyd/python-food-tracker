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

# --- 2. Get the HIDDEN Numeric ID (The "Legacy" Fix) ---
print("Extracting numeric project ID...")
sync_url = "https://api.todoist.com/sync/v9/sync"
sync_data = {
    "resource_types": '["projects"]',
    "sync_token": "*"
}
headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}

try:
    sync_res = requests.post(sync_url, headers=headers, data=sync_data)
    sync_res.raise_for_status()
    # Find the project that matches your alphanumeric ID
    projects = sync_res.json().get("projects", [])
    
    # We look for the project where the 'id' (numeric) corresponds to your '6fxHrQ58...'
    # In the Sync API, the 'id' is numeric, but the 'v2_id' is your string '6fxHrQ58...'
    target_project = next((p for p in projects if p.get("v2_id") == ALPHANUMERIC_PROJECT_ID), None)
    
    if not target_project:
        print(f"❌ Could not find project with v2_id: {ALPHANUMERIC_PROJECT_ID}")
        exit(1)
        
    NUMERIC_ID = target_project["id"]
    print(f"✅ Found Legacy Numeric ID: {NUMERIC_ID}")

except Exception as e:
    print(f"❌ Failed to map IDs: {e}")
    exit(1)

# --- 3. Fetch Today's Completions ---
# Now we use that NUMERIC_ID which the endpoint actually understands
SYNC_COMPLETED_URL = "https://api.todoist.com/sync/v9/completed/get_all"
# ... (rest of your params and since_str logic)
params = {
    "project_id": NUMERIC_ID, 
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
