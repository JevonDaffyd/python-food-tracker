#!/usr/bin/env python3
"""
Rebuild Todoist project from local CSVs (safe, robust, /api/v1 endpoints).

- Normalizes different list response shapes (dict with 'results'/'items', list of dicts, list of ids).
- Uses BASE_DIR for CSV paths.
- Handles 410 API_DEPRECATED and surfaces error_extra.
- Adds small retry/backoff for create/delete operations.
- Generates 30-day performance chart showing daily unique food counts.
- Commits chart to git on docs/ folder for GitHub Pages.
"""
import os
import time
import json
import requests
import pandas as pd
import subprocess
from datetime import datetime, timedelta

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
DOCS_DIR = os.path.join(BASE_DIR, "docs")
CHART_PATH = os.path.join(DOCS_DIR, "index.html")

# Ensure docs directory exists
os.makedirs(DOCS_DIR, exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {TODOIST_TOKEN}",
    "Content-Type": "application/json",
}

API_BASE = "https://api.todoist.com/api/v1"
URL_TASKS = f"{API_BASE}/tasks"

# --- Utility: exponential backoff wrapper for requests ---
def with_retries(func, max_attempts=4, base_delay=0.5, *args, **kwargs):
    attempt = 0
    while True:
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt >= max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"Transient error: {e}. Retrying in {delay:.1f}s (attempt {attempt}/{max_attempts})...")
            time.sleep(delay)


def generate_performance_chart(food_record_df):
    """Generate 30-day performance chart HTML with daily and rolling 7-day unique food counts."""
    print("Generating performance chart...")
    
    # Setup timeline ranges
    today = pd.Timestamp.now().normalize()
    thirty_days_ago = today - pd.Timedelta(days=29)
    start_for_rolling = thirty_days_ago - pd.Timedelta(days=6)  # lookback window for accurate week-1 rolling math
    
    food_record_df['Date'] = pd.to_datetime(food_record_df['Date'], errors='coerce')
    
    # Create complete date range from lookback to today
    full_range = pd.date_range(start=start_for_rolling, end=today, freq='D')
    
    # Map food entries to sets per day to handle deduplication easily
    foods_by_date = food_record_df.groupby('Date')['Food'].apply(set).reindex(full_range, fill_value=set())
    
    daily_counts = []
    rolling_7_counts = []
    
    # Compute calculations across the complete timeline
    for i in range(len(full_range)):
        daily_counts.append(len(foods_by_date.iloc[i]))
        
        # Pull sliding 7-day window
        start_idx = max(0, i - 6)
        combined_window = set().union(*foods_by_date.iloc[start_idx:i+1])
        rolling_7_counts.append(len(combined_window))
        
    # Slice down to just the final 30 days intended for presentation
    chart_dates = [d.strftime('%Y-%m-%d') for d in full_range[-30:]]
    chart_daily = daily_counts[-30:]
    chart_rolling = rolling_7_counts[-30:]
    
    # Text metrics for dashboard boxes
    today_rolling_val = chart_rolling[-1]
    avg_30_val = sum(chart_daily) / len(chart_daily) if chart_daily else 0
    best_day_val = max(chart_daily) if chart_daily else 0
    days_above_30_val = sum(1 for c in chart_daily if c >= 30)
    
    # Generate unified HTML layout
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Food Tracker - 30 Day Performance</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 16px; margin: 0; }}
        .container {{ max-width: 100%; background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ margin: 0 0 8px 0; font-size: 24px; color: #333; }}
        .subtitle {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        #chartContainer {{ position: relative; height: 400px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 20px; }}
        .stat-box {{ background: #f9f9f9; padding: 12px; border-radius: 6px; border-left: 4px solid #4CAF50; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; font-weight: 600; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #333; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🥗 Food Tracker Performance</h1>
        <p class="subtitle">30-day view with rolling 7-day unique counts ({chart_dates[0]} to {chart_dates[-1]})</p>
        
        <div id="chartContainer">
            <canvas id="performanceChart"></canvas>
        </div>
        
        <div class="stats">
            <div class="stat-box" style="border-left-color: #2196F3;">
                <div class="stat-label">Today's 7-Day Unique Count</div>
                <div class="stat-value">{today_rolling_val} foods</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">30-Day Average (daily)</div>
                <div class="stat-value">{avg_30_val:.1f} foods</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Best Day (daily)</div>
                <div class="stat-value">{best_day_val} foods</div>
            </div>
            <div class="stat-box" style="border-left-color: #FF9800;">
                <div class="stat-label">Days Above 30 (daily)</div>
                <div class="stat-value">{days_above_30_val} days</div>
            </div>
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('performanceChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(chart_dates)},
                datasets: [
                    {{
                        label: 'Daily Unique Foods',
                        data: {json.dumps(chart_daily)},
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.08)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4
                    }},
                    {{
                        label: 'Rolling 7‑Day Unique Foods',
                        data: {json.dumps(chart_rolling)},
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.06)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 3
                    }},
                    {{
                        label: 'Target (30 foods)',
                        data: Array({len(chart_dates)}).fill(30),
                        borderColor: '#FF9800',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        fill: false,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top' }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y}}`,
                            afterBody: ctx => {{
                                if (ctx[0].dataset.label === 'Rolling 7‑Day Unique Foods') {{
                                    const val = ctx[0].parsed.y;
                                    return val >= 30 ? '✓ Goal met (7-day)!' : `${{30 - val}} to 30 (7-day)`;
                                }}
                                return '';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ ticks: {{ maxTicksLimit: 8 }} }},
                    y: {{ beginAtZero: true, ticks: {{ stepSize: 5 }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open(CHART_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Chart generated successfully: {CHART_PATH}")


# --- 1. LOAD DATA (scheduled before midnight) ---
print("Loading CSV data...")
try:
    food_record = pd.read_csv(CSV_FOOD_RECORD)
except FileNotFoundError:
    food_record = pd.DataFrame(columns=["Date", "Food"])

try:
    food_reference = pd.read_csv(CSV_FOOD_REFERENCE)
except FileNotFoundError:
    print(f"❗ {CSV_FOOD_REFERENCE} not found. Create it with a 'Food' column.")
    raise SystemExit(1)

# --- 2. SYNC & CALCULATE PRIORITIES (scheduled after midnight) ---
print("Calculating stats and priorities...")
today = pd.Timestamp.now().normalize()
seven_days_ago = today - pd.Timedelta(days=6)  # last 7 days inclusive

recent_df = food_record[pd.to_datetime(food_record['Date']) >= seven_days_ago].copy()
recent_unique_count = recent_df['Food'].nunique()
remaining_goal = max(TARGET_GOAL - recent_unique_count, 0)

print(f"Unique foods eaten in last 7 days: {recent_unique_count}")
print(f"Remaining target for today: {remaining_goal}")

# Build stats
if not food_record.empty:
    stats = food_record.groupby('Food').agg(
        Latest_Date=('Date', 'max'),
        Count=('Date', 'count')
    ).reset_index()
else:
    stats = pd.DataFrame(columns=['Food', 'Latest_Date', 'Count'])

# Ensure reference has expected columns
if 'Last_Date_Eaten' not in food_reference.columns:
    food_reference['Last_Date_Eaten'] = pd.NA
if 'Total_Count' not in food_reference.columns:
    food_reference['Total_Count'] = 0

stats_indexed = stats.set_index('Food')
latest = food_reference['Food'].map(stats_indexed['Latest_Date'])
latest = pd.to_datetime(latest, errors='coerce')
latest_str = latest.dt.strftime("%Y-%m-%d")

food_reference['Last_Date_Eaten'] = latest_str.fillna(food_reference['Last_Date_Eaten'])

food_reference['Total_Count'] = food_reference['Food'].map(
    stats_indexed['Count']
).fillna(0).astype(int)

food_reference['Days_Since_Eaten'] = (
    today - pd.to_datetime(food_reference['Last_Date_Eaten'])
).dt.days.fillna(999).astype(int)

def get_priority(days):
    if days >= 7:
        return 4
    if 5 <= days <= 6:
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

# --- 3b. GENERATE PERFORMANCE CHART ---
generate_performance_chart(food_record)

# --- 4. REBUILD TODOIST PROJECT (use /api/v1 endpoints) ---
print("Cleaning and rebuilding Todoist project...")

# 4a. List existing tasks in the project (active tasks)
try:
    resp = with_retries(lambda: requests.get(URL_TASKS, headers=HEADERS, params={"project_id": PROJECT_ID}, timeout=30))
except requests.exceptions.RequestException as e:
    print("❌ Failed to list existing tasks:", e)
    raise SystemExit(1)

# Handle 410 API_DEPRECATED explicitly
if resp.status_code == 410:
    try:
        err = resp.json()
        extra = err.get("error_extra", {})
        print("❌ Todoist API returned 410 API_DEPRECATED. Details:", json.dumps(extra))
    except Exception:
        print("❌ Todoist API returned 410 API_DEPRECATED (no JSON body).")
    raise SystemExit(1)

try:
    resp.raise_for_status()
except requests.exceptions.HTTPError as e:
    print("❌ HTTP error when listing tasks:", e)
    print("Response body:", resp.text)
    raise SystemExit(1)

existing_tasks = resp.json()

# --- 4b. Normalize response shape to a list of task entries ---
if isinstance(existing_tasks, dict):
    if isinstance(existing_tasks.get("results"), list):
        source_list = existing_tasks["results"]
    elif isinstance(existing_tasks.get("items"), list):
        source_list = existing_tasks["items"]
    else:
        # find first list value if present
        found = None
        for v in existing_tasks.values():
            if isinstance(v, list):
                found = v
                break
        source_list = found or []
elif isinstance(existing_tasks, list):
    source_list = existing_tasks
else:
    source_list = []

# Debugging info (helpful in CI logs)
print(f"DEBUG: normalized source_list length = {len(source_list)}; sample types: {[type(x) for x in source_list[:3]]}")

def extract_task_id(entry):
    if isinstance(entry, dict):
        return entry.get("id") or entry.get("task_id") or entry.get("id_str")
    if isinstance(entry, str):
        return entry
    return None

task_ids = []
for entry in source_list:
    tid = extract_task_id(entry)
    if tid:
        task_ids.append(tid)
    else:
        print("Warning: skipping unexpected task entry (not dict or id string):", repr(entry)[:200])

# 4c. Delete existing tasks (tolerant of different delete status codes)
deleted_count = 0
for task_id in task_ids:
    def do_delete():
        return requests.delete(f"{URL_TASKS}/{task_id}", headers=HEADERS, timeout=15)
    try:
        del_resp = with_retries(do_delete, max_attempts=3, base_delay=0.2)
    except requests.exceptions.RequestException as e:
        print(f"Error deleting task {task_id}: {e}")
        continue

    if del_resp.status_code == 410:
        try:
            err = del_resp.json()
            extra = err.get("error_extra", {})
            print("❌ Delete returned 410 API_DEPRECATED. Details:", json.dumps(extra))
        except Exception:
            print("❌ Delete returned 410 API_DEPRECATED (no JSON body).")
        raise SystemExit(1)

    if not (200 <= del_resp.status_code < 300):
        print(f"Warning: delete returned {del_resp.status_code} for task {task_id}: {del_resp.text}")
    else:
        deleted_count += 1
    time.sleep(0.12)

print(f"Deleted {deleted_count} existing tasks (attempted {len(task_ids)}).")

# 4d. Create parent task (high priority summary)

# Build parent task content based on progress
if remaining_goal <= 0:
    # Already hit the 30‑foods target
    parent_content = (
        f"Eat some plant foods. You've already had {recent_unique_count} "
        f"in the last 7 days! ({datetime.now().strftime('%d %b')})\n\n"
        f"📊 [View 30-day performance](https://jevondaffyd.github.io/python-food-tracker/)"
    )
else:
    # Still below target
    parent_content = (
        f"Eat {remaining_goal} plant foods today "
        f"({datetime.now().strftime('%d %b')})\n\n"
        f"📊 [View 30-day performance](https://jevondaffyd.github.io/python-food-tracker/)"
    )

parent_payload = {
    "content": parent_content,
    "project_id": PROJECT_ID,
    "due_string": "today",
    "priority": 4
}

def create_task(payload):
    return requests.post(URL_TASKS, headers=HEADERS, json=payload, timeout=30)

try:
    parent_resp = with_retries(lambda: create_task(parent_payload), max_attempts=4, base_delay=0.3)
except requests.exceptions.RequestException as e:
    print("❌ Failed to create parent task:", e)
    raise SystemExit(1)

if parent_resp.status_code == 410:
    try:
        err = parent_resp.json()
        extra = err.get("error_extra", {})
        print("❌ Create parent returned 410 API_DEPRECATED. Details:", json.dumps(extra))
    except Exception:
        print("❌ Create parent returned 410 API_DEPRECATED (no JSON body).")
    raise SystemExit(1)

try:
    parent_resp.raise_for_status()
except requests.exceptions.HTTPError as e:
    print("❌ Parent create HTTP error:", e)
    print("Response body:", parent_resp.text)
    raise SystemExit(1)

parent_task = parent_resp.json()
parent_id = parent_task.get("id")
if not parent_id:
    print("❌ Parent task created but no id returned:", parent_resp.text)
    raise SystemExit(1)
# 4e. Create child tasks from reference sheet
created_count = 0
for _, row in food_reference.iterrows():
    content = str(row.get('Food', '')).strip()
    if not content:
        continue

    # Format last eaten date
    last_date_raw = row.get('Last_Date_Eaten')
    if pd.isna(last_date_raw):
        last_eaten_str = "Never"
    else:
        last_eaten_str = pd.to_datetime(last_date_raw).strftime("%d/%m/%y")

    description = (
        f"Last eaten: {last_eaten_str}\n"
        f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    child_payload = {
        "content": content,
        "project_id": PROJECT_ID,
        "parent_id": parent_id,
        "priority": int(row.get('Todoist_Priority', 1)),
        "description": description
    }

    try:
        c_resp = with_retries(lambda: create_task(child_payload), max_attempts=3, base_delay=0.2)
    except requests.exceptions.RequestException as e:
        print(f"Error creating task '{content}': {e}")
        continue

    if c_resp.status_code == 410:
        try:
            err = c_resp.json()
            extra = err.get("error_extra", {})
            print("❌ Create child returned 410 API_DEPRECATED. Details:", json.dumps(extra))
        except Exception:
            print("❌ Create child returned 410 API_DEPRECATED (no JSON body).")
        raise SystemExit(1)

    if not (200 <= c_resp.status_code < 300):
        print(f"Warning: create child returned {c_resp.status_code} for '{content}': {c_resp.text}")
    else:
        created_count += 1

    time.sleep(0.18)

print(f"✨ Done. Created {created_count} child tasks under parent {parent_id}.")
