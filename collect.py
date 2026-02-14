#!/usr/bin/env python3
import os, sys, json, requests
from datetime import datetime, timezone, time

TOKEN = os.environ.get("TODOIST_TOKEN")
if not TOKEN:
    print("Missing TODOIST_TOKEN"); sys.exit(2)

# Build a reasonable since/until for today in UTC (adjust if you want local)
today = datetime.now(timezone.utc).date()
since = datetime.combine(today, time.min, tzinfo=timezone.utc).isoformat()
until = datetime.combine(today, time.max, tzinfo=timezone.utc).isoformat()

URL = "https://api.todoist.com/api/v1/tasks/completed/by_completion_date"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Try as GET first; if the endpoint requires POST you can switch to requests.post
params = {"since": since, "until": until, "limit": 50}

print("Calling:", URL)
try:
    r = requests.get(URL, headers=headers, params=params, timeout=20)
except Exception as e:
    print("Network error:", e); sys.exit(1)

print("Status:", r.status_code)
print("Headers:")
for k, v in r.headers.items():
    print(f"  {k}: {v}")

# Try to parse JSON safely and print a truncated preview
text = r.text or ""
print("\nBody preview (first 4000 chars):")
print(text[:4000])

# If JSON, pretty-print top-level keys and a small sample
try:
    j = r.json()
    if isinstance(j, dict):
        print("\nTop-level keys:", ", ".join(sorted(j.keys())))
    elif isinstance(j, list):
        print("\nTop-level: list with length", len(j))
    print("\nJSON sample (first item or snippet):")
    if isinstance(j, list) and j:
        print(json.dumps(j[0], indent=2)[:4000])
    elif isinstance(j, dict):
        print(json.dumps({k: j[k] for k in list(j)[:10]}, indent=2)[:4000])
except Exception:
    pass

# If 410, surface error_extra if present
if r.status_code == 410:
    try:
        err = r.json()
        print("\nAPI_DEPRECATED details:", json.dumps(err.get("error_extra", {}), indent=2))
    except Exception:
        pass
