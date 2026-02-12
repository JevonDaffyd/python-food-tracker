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

# --- 2. INGEST TODAY'S COMPLETED ITEMS ---
print("Checking Todoist for today's completions...")
url_sync = "https://api.todoist.com/sync/v9/completed/get_all"
res = requests.get(url_sync, headers=headers, params={"project_id": PROJECT_ID, "limit": 50})

if res.status_code == 200:
    completed_items = res.json().get('items', [])
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_entries = []
    for item in completed_items:
        completion_date = item['completed_at'].split('T')[0]
        if completion_date == today_str:
            food_name = item['content']
            # Avoid duplicates
            if not ((food_record['Date'] == today_str) & (food_record['Food'] == food_name)).any():
                new_entries.append({"Date": today_str, "Food": food_name})
                print(f"Logged: {food_name}")

    if new_entries:
        food_record = pd.concat([food_record, pd.DataFrame(new_entries)], ignore_index=True)
        food_record.to_csv(os.path.join(BASE_DIR, "food_record.csv"), index=False, encoding="utf-8")
else:
    print(f"Error fetching completions: {res.text}")
