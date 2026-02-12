# --- 1. SETUP & DATA LOADING (THIS NEEDS SCHEDULED BEFORE MIDNIGHT) ---
import pandas as pd
import requests
import time
from datetime import datetime, date
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# NEW: official Todoist SDK
from todoist_api_python.api import TodoistAPI

TODOIST_TOKEN = os.environ["TODOIST_TOKEN"]
PROJECT_ID = "6fxHrQ58f8jFXp24"
TARGET_GOAL = 30

# headers kept for compatibility with other code, but not used for SDK calls
headers = {
    "Authorization": f"Bearer {TODOIST_TOKEN}",
    "Content-Type": "application/json",
}

# Load your files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
food_record = pd.read_csv(os.path.join(BASE_DIR, "food_record.csv"))
food_reference = pd.read_csv(os.path.join(BASE_DIR, "food_reference.csv"))

print(f"Loaded food_record with columns: {list(food_record.columns)}", flush=True)
print(f"Food record shape: {food_record.shape}", flush=True)

# --- 2. INGEST TODAY'S COMPLETED ITEMS ---
print("Checking Todoist for today's completions...", flush=True)

# --- SDK fetch (replace your existing fetch block with this) ---
api = TodoistAPI(TODOIST_TOKEN)

today_date = date.today()
since = f"{today_date}T00:00:00"
until = f"{today_date}T23:59:59"

try:
    completed_items_raw = api.get_completed_tasks_by_completion_date(
        since=since,
        until=until,
        project_id=PROJECT_ID,
        limit=200
    )
except AttributeError:
    available = [m for m in dir(api) if m.startswith("get_completed")]
    raise RuntimeError(
        "Todoist SDK in this environment does not expose "
        "'get_completed_tasks_by_completion_date'. Available methods: "
        f"{available}. Check the SDK docs or upgrade the package."
    )
except Exception as exc:
    raise SystemExit(f"Error fetching completed items from Todoist SDK: {exc}")

# Normalize SDK return (list of dicts or objects)
normalized_items = []
for it in completed_items_raw:
    if isinstance(it, dict):
        normalized_items.append(it)
    else:
        # try to convert object to dict by attribute access
        content = getattr(it, "content", None) or getattr(it, "task", None)
        completed_at = getattr(it, "completed_at", None) or getattr(it, "completed_date", None)
        if content and completed_at:
            normalized_items.append({"content": content, "completed_at": completed_at})

today_str = datetime.now().strftime('%Y-%m-%d')
print(f"✓ Found {len(normalized_items)} completed items (SDK)", flush=True)
print(f"Today's date: {today_str}", flush=True)

new_entries = []
for item in normalized_items:
    completed_at = item.get("completed_at")
    content = item.get("content")
    if not completed_at or not content:
        continue
    completion_date = completed_at.split('T')[0]
    if completion_date == today_str:
        food_name = content
        # Avoid duplicates
        if not ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any():
            new_entries.append({"Date": today_str, "Food": food_name})
            print(f"  ✓ Logged: {food_name}", flush=True)
        else:
            print(f"  ✗ Duplicate skipped: {food_name}", flush=True)

if new_entries:
    print(f"\nAdding {len(new_entries)} new entries to food_record...", flush=True)
    food_record = pd.concat([food_record, pd.DataFrame(new_entries)], ignore_index=True)

    csv_path = os.path.join(BASE_DIR, "food_record.csv")
    food_record.to_csv(csv_path, index=False, encoding="utf-8")

    print(f"✓ Successfully wrote {len(new_entries)} new entries to food_record.csv", flush=True)
    print(f"✓ CSV file location: {csv_path}", flush=True)
    print(f"✓ New total rows: {len(food_record)}", flush=True)
else:
    print("ℹ No new entries to log (all items already recorded or none completed today)", flush=True)
