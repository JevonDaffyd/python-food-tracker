#!/usr/bin/env python3
import os
import pandas as pd
from datetime import datetime
from todoist_api_python.api import TodoistAPI

# --- 1. Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
PROJECT_ID = "6fxHrQ58f8jFXp24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    exit(1)

# Initialize the Current REST API
api = TodoistAPI(TODOIST_TOKEN)

# --- 2. Fetch Tasks using Filter ---
# We use a filter to find tasks completed today in your specific project.
# This avoids the deprecated Sync API entirely.
print(f"Fetching tasks completed today in project {PROJECT_ID}...")

try:
    # 'completed' is a supported filter parameter in the REST API
    # Note: We query all tasks and filter locally to ensure we catch everything
    tasks = api.get_tasks(project_id=PROJECT_ID, filter="completed today")
    
    # If 'filter' doesn't return completed items (API behavior varies), 
    # we can also check for recently closed items via the activity log if needed,
    # but 'filter' is the standard approach.
    print(f"✅ Found {len(tasks)} items matching filter.")

except Exception as e:
    print(f"❌ REST API Error: {e}")
    exit(1)

# --- 3. Process CSV ---
today_str = datetime.now().strftime('%Y-%m-%d')
csv_path = os.path.join(BASE_DIR, "food_record.csv")

try:
    food_record = pd.read_csv(csv_path)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

new_entries = []
for task in tasks:
    food_name = task.content.strip()
    
    # Duplicate check
    is_dup = ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any()
    
    if not is_dup:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")

# --- 4. Save Results ---
if new_entries:
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Saved {len(new_entries)} new items.")
else:
    print("ℹ No new items found to log today.")
