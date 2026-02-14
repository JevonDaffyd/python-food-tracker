import pandas as pd
import requests
import os
from datetime import datetime, timezone
from todoist_api_python.api import TodoistAPI

# --- Configuration ---
TODOIST_API_TOKEN = "YOUR_API_TOKEN"  # Get this from Todoist Settings -> Integrations
PROJECT_ID = "6fxHrQ58f8jFXp24"       # The ID from your browser URL
FOOD_RECORD_PATH = 'food_record.csv'
FOOD_REFERENCE_PATH = 'food_reference.csv'

def get_completed_tasks_today(token, project_id):
    """
    Fetches tasks completed today from a specific project.
    Uses Sync API v9 as the REST SDK does not support archived/completed items.
    """
    url = "https://api.todoist.com/sync/v9/completed/get_all"
    
    # Calculate UTC midnight for "today"
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since_str = today_start.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "project_id": project_id,
        "since": since_str,
        "limit": 50
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    # The Sync API returns a list of items in the 'items' key
    return response.json().get("items", [])

def sync_food_logs():
    # 1. Initialize Official SDK to verify connection
    api = TodoistAPI(TODOIST_API_TOKEN)
    try:
        project = api.get_project(project_id=PROJECT_ID)
        print(f"Successfully connected to project: {project.name}")
    except Exception as e:
        print(f"Failed to connect to Todoist: {e}")
        return

    # 2. Fetch completed tasks via Sync API
    completed_items = get_completed_tasks_today(TODOIST_API_TOKEN, PROJECT_ID)
    if not completed_items:
        print("No tasks completed so far today.")
        return

    # 3. Load Local Data using Pandas
    try:
        df_record = pd.read_csv(FOOD_RECORD_PATH)
    except FileNotFoundError:
        df_record = pd.DataFrame(columns=['Date', 'Food'])

    # 4. Process new items
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_entries = []

    for item in completed_items:
        food_name = item.get('content')
        
        # Check if this food has already been logged today to prevent duplicates
        is_already_logged = ((df_record['Date'] == today_str) & 
                             (df_record['Food'] == food_name)).any()
        
        if not is_already_logged:
            new_entries.append({'Date': today_str, 'Food': food_name})
            print(f"New log found: {food_name}")

    # 5. Save updates to CSV
    if new_entries:
        df_new = pd.DataFrame(new_entries)
        df_updated = pd.concat([df_record, df_new], ignore_index=True)
        df_updated.to_csv(FOOD_RECORD_PATH, index=False)
        print(f"CSV updated with {len(new_entries)} new entries.")
    else:
        print("Everything is already up to date.")

if __name__ == "__main__":
    sync_food_logs()
