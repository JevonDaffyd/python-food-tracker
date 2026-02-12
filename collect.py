# --- 1. SETUP & DATA LOADING (THIS NEEDS SCHEDULED BEFORE MIDNIGHT) ---
import pandas as pd
import time
from datetime import datetime, date
import os

# NEW: import the official Todoist SDK
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

print(f"Loaded food_record with columns: {list(food_record.columns)}")
print(f"Food record shape: {food_record.shape}")

# --- 2. INGEST TODAY'S COMPLETED ITEMS ---
print("Checking Todoist for today's completions...")

# Initialize SDK client
api = TodoistAPI(TODOIST_TOKEN)

# Use SDK to fetch completed items for today
today_date = date.today()
since = f"{today_date}T00:00:00"
until = f"{today_date}T23:59:59"

# The SDK method name may vary by version; try the most likely method and handle AttributeError
completed_items = []
try:
    # Most recent official SDK exposes a method to fetch completed tasks/items by date range.
    # Try the common method name first.
    completed_items = api.get_completed_tasks(since=since, until=until, project_id=PROJECT_ID, limit=200)
except AttributeError:
    try:
        # Alternate method name some versions use
        completed_items = api.get_completed_items(since=since, until=until, project_id=PROJECT_ID, limit=200)
    except AttributeError:
        # If neither method exists, raise a clear error so you can check the installed SDK version
        raise RuntimeError(
            "Installed todoist SDK does not expose a completed-items method named "
            "'get_completed_tasks' or 'get_completed_items'. "
            "Check the SDK docs for the correct method name for your version."
        )
except Exception as exc:
    # Any other runtime error from the SDK
    raise SystemExit(f"Error fetching completed items from Todoist SDK: {exc}")

# The SDK may return a list of dicts or objects; normalize to dicts
normalized_items = []
for it in completed_items:
    if isinstance(it, dict):
        normalized_items.append(it)
    else:
        # try to convert object to dict by attribute access
        try:
            normalized_items.append({
                "content": getattr(it, "content", None) or getattr(it, "task", None),
                "completed_at": getattr(it, "completed_at", None) or getattr(it, "completed_date", None)
            })
        except Exception:
            # fallback: skip items we can't parse
            continue

today_str = datetime.now().strftime('%Y-%m-%d')
print(f"✓ Found {len(normalized_items)} completed items (SDK)")
print(f"Today's date: {today_str}")

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
            print(f"  ✓ Logged: {food_name}")
        else:
            print(f"  ✗ Duplicate skipped: {food_name}")

if new_entries:
    print(f"\nAdding {len(new_entries)} new entries to food_record...")
    food_record = pd.concat([food_record, pd.DataFrame(new_entries)], ignore_index=True)

    csv_path = os.path.join(BASE_DIR, "food_record.csv")
    food_record.to_csv(csv_path, index=False, encoding="utf-8")

    print(f"✓ Successfully wrote {len(new_entries)} new entries to food_record.csv")
    print(f"✓ CSV file location: {csv_path}")
    print(f"✓ New total rows: {len(food_record)}")
else:
    print("ℹ No new entries to log (all items already recorded or none completed today)")
        print("ℹ No new entries to log (all items already recorded or none completed today)")
else:
    print(f"✗ Error fetching completions: {res.status_code}")
    print(f"✗ Response: {res.text}")
