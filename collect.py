#!/usr/bin/env python3
import requests
import os
import pandas as pd
from datetime import datetime, timezone
from todoist_api_python.api import TodoistAPI

# --- 1. Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
PROJECT_ID = "6fxHrQ58f8jFXp24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 2. Connection & Validation ---
if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found in environment.")
    exit(1)

api = TodoistAPI(TODOIST_TOKEN)

try:
    # Verify project exists and token is valid
    project = api.get_project(project_id=PROJECT_ID)
    print(f"✅ Connected to: {project.name}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# --- 3. Fetch Today's Completions (Sync API v9) ---
print("Checking Todoist for today's completions...")

# The Sync API is the current standard for fetching completed items
SYNC_URL = "https://api.todoist.com/sync/v9/completed/get_all"

# Calculate UTC midnight today
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
since_str = today_start.strftime('%Y-%m-%dT%H:%M:%SZ')

headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
params = {
    "project_id": PROJECT_ID,
    "since": since_str,
    "limit": 100
}

try:
    response = requests.get(SYNC_URL, headers=headers, params=params)
    response.raise_for_status()
    completed_data = response.json()
    completed_items = completed_data.get("items", [])
    print(f"✓ Found {len(completed_items)} completed items since {since_str}")
except requests.exceptions.RequestException as e:
    print(f"❌ Error fetching from Sync API: {e}")
    exit(1)

# --- 4. Process CSV and Log New Entries ---
today_str = datetime.now().strftime('%Y-%m-%d')
csv_path = os.path.join(BASE_DIR, "food_record.csv")

try:
    food_record = pd.read_csv(csv_path)
except FileNotFoundError:
    print("ℹ food_record.csv not found, creating new one.")
    food_record = pd.DataFrame(columns=["Date", "Food"])

new_entries = []
for item in completed_items:
    food_name = item.get('content', '').strip()
    if not food_name:
        continue
    
    # Check for duplicates in current file
    is_duplicate = ((food_record['Date'] == today_str) & 
                    (food_record['Food'] == food_name)).any()
    
    if not is_duplicate:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")
    else:
        print(f"  ✗ Duplicate skipped: {food_name}")

# --- 5. Save Results ---
if new_entries:
    print(f"\nAdding {len(new_entries)} new entries to food_record...")
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Successfully wrote to {csv_path}")
else:
    print("ℹ No new entries to log.")
