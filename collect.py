import os
from todoist_api_python.api import TodoistAPI

# 1. Get token from environment
token = os.environ.get("TODOIST_TOKEN")

if not token:
    print("❌ Error: TODOIST_TOKEN environment variable is empty.")
    exit(1)

# 2. Initialize API
api = TodoistAPI(token)
project_id = "6fxHrQ58f8jFXp24"

try:
    # Attempt to fetch your specific project
    project = api.get_project(project_id=project_id)
    print("✅ Connection Successful!")
    print(f"✅ Project Found: {project.name}")
    print(f"✅ API Version: REST v2 (Current)")
    
except Exception as error:
    print("❌ Connection Failed.")
    print(f"Details: {error}")
    exit(1)
