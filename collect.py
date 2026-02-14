#!/usr/bin/env python3
import os
import requests
import pandas as pd
from datetime import datetime

# --- 1. Configuration ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
PROJECT_ID = "6fxHrQ58f8jFXp24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not found.")
    exit(1)

# --- 2. Fetch Tasks via REST v2 (Direct Request) ---
# We use the 'filter' parameter to get tasks completed today.
# The REST API returns active tasks, but 'completed' items can be tracked 
# by checking for tasks that are closed/completed within the current session.
URL = "https://api.todoist.com/rest/v2/tasks"
headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
params = {
    "project_id": PROJECT_ID,
    "filter": "completed today" 
}

print(f"Fetching tasks from project {PROJECT_ID}...")

try:
    response = requests.get(URL, headers=headers, params=params)
    response.raise_for_status()
    tasks = response.json()
    print(f"✅ API Response Received. Found {len(tasks)} items.")
except requests.exceptions.RequestException as e:
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
    food_name = task.get("content", "").strip()
    
    # Duplicate check for today
    is_dup = ((food_record['Date'] == today_str) & 
              (food_record['Food'] == food_name)).any()
    
    if not is_dup:
        new_entries.append({"Date": today_str, "Food": food_name})
        print(f"  ✓ Logged: {food_name}")

# --- 4. Save Results ---
if new_entries:
    new_df = pd.DataFrame(new_entries)
    food_record = pd.concat([food_record, new_df], ignore_index=True)
    food_record.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ Successfully updated {csv_path}")
else:
    print("ℹ No new items found to log for today.")
