# --- 1. SETUP & DATA LOADING (THIS NEEDS SCHEDULED BEFORE MIDNIGHT) ---
import pandas as pd
import requests
import time
from datetime import datetime
import os

TODOIST_TOKEN = os.environ["TODOIST_TOKEN"] 
PROJECT_ID = "6fxHrQ58f8jFXp24" 
TARGET_GOAL = 30 

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
url_sync = "https://api.todoist.com/rest/v2/tasks"
res = requests.get(url_sync, headers=headers)

if res.status_code == 200:
    all_tasks = res.json()
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"✓ Found {len(all_tasks)} tasks")
    print(f"Today's date: {today_str}")
    
    new_entries = []
    for task in all_tasks:
        # Check if task is completed and completed today
        if task.get('is_completed') and task.get('completed_at'):
            completion_date = task['completed_at'].split('T')[0]
            if completion_date == today_str:
                food_name = task['content']
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
else:
    print(f"✗ Error fetching tasks: {res.status_code}")
    print(f"✗ Response: {res.text}")
