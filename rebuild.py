#!/usr/bin/env python3
"""
Rebuild Todoist project from local reference CSVs.

Assumptions:
- You validated the /api/v1 completed endpoint earlier and want all task operations
  to use the /api/v1 prefix.
- TODOIST_TOKEN is provided as a GitHub Actions secret.
"""
import os
import time
import json
import requests
import pandas as pd
from datetime import datetime, timezone

# --- Config ---
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")
if not TODOIST_TOKEN:
    print("❌ Error: TODOIST_TOKEN not set in environment.")
    raise SystemExit(1)

PROJECT_ID = "6fxHrQ58f8jFXp24"
TARGET_GOAL = 30
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FOOD_RECORD = os.path.join(BASE_DIR, "food_record.csv")
CSV_FOOD_REFERENCE = os.path.join(BASE_DIR, "food_reference.csv")

HEADERS = {
    "Authorization": f"Bearer {TODOIST_TOKEN}",
    "Content-Type": "application/json",
}

# --- 1. LOAD DATA ---
print("Loading CSV data...")
try:
    food_record = pd.read_csv(CSV_FOOD_RECORD)
except FileNotFoundError:
    # If the record doesn't exist yet, create an empty frame with expected columns
    food_record = pd.DataFrame(columns=["Date", "Food"])

try:
    food_reference = pd.read_csv(CSV_FOOD_REFERENCE)
except FileNotFoundError:
    print(f"❗ {CSV_FOOD_REFERENCE} not found. Create it with a 'Food' column.")
    raise SystemExit(1)

# --- 2. SYNC & CALCULATE PRIORITIES ---
print("Calculating stats and priorities...")


today = pd.Timestamp.now().normalize()
seven_days_ago = today - pd.Timedelta(days=6)  

recent_df = food_record[pd.to_datetime(food_record['Date']) >= seven_days_ago].copy()
recent_unique_count = recent_df['Food'].nunique()
remaining_goal = max(TARGET_GOAL - recent_unique_count, 0)

print(f"Unique foods eaten in last 7 days: {recent_unique_count}")
print(f"Remaining target for today: {remaining_goal}")

# Build stats
stats = food_record.groupby('Food').agg(
    Latest_Date=('Date', 'max'),
    Count=('Date', 'count')
).reset_index()

# Map stats into reference sheet safely
if 'Last_Date_Eaten' not in food_reference.columns:
    food_reference['Last_Date_Eaten'] = pd.NA
if 'Total_Count' not in food_reference.columns:
    food_reference['Total_Count'] = 0

stats_indexed = stats.set_index('Food')
food_reference['Last_Date_Eaten'] = food_reference['Food'].map(
    stats_indexed['Latest_Date']
).fillna(food_reference['Last_Date_Eaten'])

food_reference['Total_Count'] = food_reference['Food'].map(
    stats_indexed['Count']
).fillna(0).astype(int)

# Days since eaten (fill missing with large number)
food_reference['Days_Since_Eaten'] = (
    today - pd.to_datetime(food_reference['Last_Date_Eaten'])
).dt.days.fillna(999).astype(int)

def get_priority(days):
    if days >= 6:
        return 4
    if days == 5:
        return 3
    if 3 <= days <= 4:
        return 2
    return 1

food_reference['Todoist_Priority'] = food_reference['Days_Since_Eaten'].apply(get_priority)
food_reference = food_reference.sort_values(by=['Todoist_Priority', 'Total_Count'], ascending=[False, False])

# --- 3. SAVE PROGRESS (persist updated reference) ---
food_record.to_csv(CSV_FOOD_RECORD, index=False)
food_reference.to_csv(CSV_FOOD_REFERENCE, index=False)
print("Local CSVs updated.")

# --- 4. REBUILD TODOIST PROJECT (use /api/v1 endpoints) ---
print("Cleaning and rebuilding Todoist project...")

API_BASE = "https://api.todoist.com/api/v1"
URL_TASKS = f"{API_BASE}/tasks"

# 4a. List existing tasks in the project (active tasks)
try:
    resp = requests.get(URL_TASKS, headers=HEADERS, params={"project_id": PROJECT_ID}, timeout=30)
    resp.raise_for_status()
    existing_tasks = resp.json()
except requests.exceptions.RequestException as e:
    print("❌ Failed to list existing tasks:", e)
    print("Response body (if any):", getattr(e, "response", None) and e.response.text)
    raise SystemExit(1)

# 4b. Delete existing tasks (be careful: this removes active tasks in the project)
for t in existing_tasks:
    task_id = t.get("id")
    if not task_id:
        continue
    try:
        del_resp = requests.delete(f"{URL_TASKS}/{task_id}", headers=HEADERS, timeout=15)
        # Some APIs return 204 on delete; accept any 2xx
        if not (200 <= del_resp.status_code < 300):
            print(f"Warning: delete returned {del_resp.status_code} for task {task_id}: {del_resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error deleting task {task_id}: {e}")
    time.sleep(0.12)

# 4c. Create parent task (high priority summary)
parent_payload = {
    "content": f"Eat {remaining_goal} plant foods today ({datetime.now().strftime('%d %b')})",
    "project_id": PROJECT_ID,
    "due_string": "today",
    "priority": 4
}
try:
    parent_resp = requests.post(URL_TASKS, headers=HEADERS, json=parent_payload, timeout=30)
    parent_resp.raise_for_status()
    parent_task = parent_resp.json()
    parent_id = parent_task.get("id")
    if not parent_id:
        print("❌ Parent task created but no id returned:", parent_resp.text)
        raise SystemExit(1)
except requests.exceptions.RequestException as e:
    print("❌ Failed to create parent task:", e)
    print("Response body:", getattr(e, "response", None) and e.response.text)
    raise SystemExit(1)

# 4d. Create child tasks from reference sheet
created_count = 0
for _, row in food_reference.iterrows():
    content = str(row.get('Food', '')).strip()
    if not content:
        continue
    child_payload = {
        "content": content,
        "project_id": PROJECT_ID,
        "parent_id": parent_id,
        "priority": int(row.get('Todoist_Priority', 1))
    }
    try:
        c_resp = requests.post(URL_TASKS, headers=HEADERS, json=child_payload, timeout=20)
        # Accept any 2xx; surface otherwise
        if not (200 <= c_resp.status_code < 300):
            print(f"Warning: create child returned {c_resp.status_code} for '{content}': {c_resp.text}")
        else:
            created_count += 1
    except requests.exceptions.RequestException as e:
        print(f"Error creating task '{content}': {e}")
    time.sleep(0.18)

print(f"✨ Done. Created {created_count} child tasks under parent {parent_id}.")
