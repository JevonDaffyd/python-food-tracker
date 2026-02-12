# --- Replace existing fetch block with this ---
print("Checking Todoist for today's completions...")

# Use the v1 endpoint that supports project_id and since/until
url = "https://api.todoist.com/api/v1/tasks/completed_by_completion_date"

# Use UTC ISO timestamps (append Z)
today = datetime.utcnow().date()
since = f"{today}T00:00:00Z"
until = f"{today}T23:59:59Z"

params = {
    "since": since,
    "until": until,
    "project_id": PROJECT_ID,
    "limit": 200,
}

completed_items = []
try:
    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    completed_items.extend(data.get("items", []))

    # Pagination: follow cursor if present
    cursor = data.get("cursor")
    while cursor:
        params["cursor"] = cursor
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        completed_items.extend(data.get("items", []))
        cursor = data.get("cursor")

    print(f"✓ Found {len(completed_items)} completed items")
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    print(f"Today's date: {today_str}")

    new_entries = []
    for item in completed_items:
        # completed_at is ISO timestamp like 2026-02-12T14:00:00Z
        completion_date = item.get('completed_at', '').split('T')[0]
        if completion_date == today_str:
            food_name = item.get('content', '').strip()
            if not food_name:
                continue
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

except requests.RequestException as e:
    print(f"✗ Error fetching completions: {getattr(e, 'response', None) and e.response.status_code or 'request error'}")
    # print server response body if available
    if hasattr(e, "response") and e.response is not None:
        print(f"✗ Response: {e.response.text[:1000]}")
    else:
        print(f"✗ Request error: {e}")
    print(f"✗ Response: {res.text}")
