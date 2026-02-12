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

# Initialize SDK client
api = TodoistAPI(TODOIST_TOKEN)

# Use SDK to fetch completed items for today
today_date = date.today()
since = f"{today_date}T00:00:00"
until = f"{today_date}T23:59:59"

def fetch_completed_with_timeout(timeout_seconds=30):
    def _fetch():
        # Try likely SDK method names; adapt if your SDK version differs
        try:
            return api.get_completed_tasks(since=since, until=until, project_id=PROJECT_ID, limit=200)
        except AttributeError:
            try:
                return api.get_completed_items(since=since, until=until, project_id=PROJECT_ID, limit=200)
            except AttributeError:
                raise RuntimeError(
                    "Installed todoist SDK does not expose a completed-items method named "
                    "'get_completed_tasks' or 'get_completed_items'. Check the SDK docs for your version."
                )

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_fetch)
        try:
            return fut.result(timeout=timeout_seconds)
        except TimeoutError:
            print(f"ERROR: Todoist fetch timed out after {timeout_seconds}s", flush=True)
            return []
        except Exception as e:
            print(f"ERROR: Todoist fetch failed: {e}", flush=True)
            return []

completed_items_raw = fetch_completed_with_timeout(timeout_seconds=30)

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
    print("ℹ No new entries to log (all items already recorded or none completed today)", flush=True)text}")
