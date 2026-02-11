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

# --- 1. SYNC & CALCULATE PRIORITIES (THIS AND BELOW NEEDS SCHEDULED AFTER MIDNIGHT) ---
print("Syncing stats and calculating priorities...")

# Load your files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
food_record = pd.read_csv(os.path.join(BASE_DIR, "food_record.csv"))
food_reference = pd.read_csv(os.path.join(BASE_DIR, "food_reference.csv"))

# Count UNIQUE foods eaten in last 7 days
today = pd.Timestamp.now().normalize()
seven_days_ago = today - pd.Timedelta(days=6)

recent_df = food_record[
    pd.to_datetime(food_record['Date']) >= seven_days_ago
].copy()

recent_unique_count = recent_df['Food'].nunique()
remaining_goal = max(TARGET_GOAL - recent_unique_count, 0)

print(f"Unique foods eaten in last 7 days: {recent_unique_count}")
print(f"Remaining target for today: {remaining_goal}")

# Existing stats logic
stats = food_record.groupby('Food').agg(
    Latest_Date=('Date', 'max'),
    Count=('Date', 'count')
).reset_index()

# Update reference sheet
food_reference['Last_Date_Eaten'] = food_reference['Food'].map(
    stats.set_index('Food')['Latest_Date']
).fillna(food_reference['Last_Date_Eaten'])

food_reference['Total_Count'] = food_reference['Food'].map(
    stats.set_index('Food')['Count']
).fillna(0).astype(int)

# Days since eaten
food_reference['Days_Since_Eaten'] = (
    today - pd.to_datetime(food_reference['Last_Date_Eaten'])
).dt.days.fillna(999).astype(int)

def get_priority(days):
    if days >= 6:
        return 4    # Red — overdue, 7 days or more
    if days == 5:
        return 3    # Orange — approaching limit
    if 3 <= days <= 4:
        return 2    # Blue — mid‑range
    return 1        # None — recently eaten

food_reference['Todoist_Priority'] = food_reference['Days_Since_Eaten'].apply(get_priority)
food_reference = food_reference.sort_values(by=['Todoist_Priority', 'Total_Count'], ascending=[False, False])

# --- 2. SAVE PROGRESS ---
food_record.to_csv('food_record.csv', index=False)
food_reference.to_csv('food_reference.csv', index=False)


# --- 3. REBUILD TODOIST LIST ---
print("Cleaning and rebuilding Todoist project...")
url_tasks = "https://api.todoist.com/rest/v2/tasks"

# Delete old tasks
existing = requests.get(url_tasks, headers=headers, params={"project_id": PROJECT_ID})
if existing.status_code == 200:
    for task in existing.json():
        requests.delete(f"{url_tasks}/{task['id']}", headers=headers)
        time.sleep(0.1)

# Create Parent
parent_resp = requests.post(url_tasks, headers=headers, json={
    "content": f"Eat {remaining_goal} plant foods today ({datetime.now().strftime('%d %b')})",
    "project_id": PROJECT_ID, "due_string": "today", "priority": 4
})

if parent_resp.status_code == 200:
    parent_id = parent_resp.json()['id']
    for _, row in food_reference.iterrows():
        requests.post(url_tasks, headers=headers, json={
            "content": row['Food'], "parent_id": parent_id, "priority": int(row['Todoist_Priority'])
        })
        time.sleep(0.2) # Avoid rate limits
    print("✨ All done! Your Todoist is fresh.")