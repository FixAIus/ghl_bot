import os
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler

# Constants
API_URL = "https://backboard.railway.app/graphql/v2"
ENABLE_LOOP = True  # Toggle this to enable/disable the loop

# Environment Variables
PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

# Utility Functions
def log(level, msg, **kwargs):
    """Centralized logger for structured JSON logging."""
    print(json.dumps({"level": level, "msg": msg, **kwargs}))

log('info', 'Starting Script')

def validate_environment():
    """Validates the required environment variables."""
    if not all([PROJECT_ID, ENVIRONMENT_ID, SERVICE_ID, API_TOKEN]):
        log("error", "Missing required environment variables.")
        exit(1)


def upsert_variable(name, value):
    """Upserts a variable in Railway."""
    log("info", f"Attempting to upsert variable: {name}", value=value)
    mutation = f"""
    mutation {{
      variableUpsert(
        input: {{
          projectId: "{PROJECT_ID}"
          environmentId: "{ENVIRONMENT_ID}"
          serviceId: "{SERVICE_ID}"
          name: "{name}"
          value: "{value}"
        }}
      )
    }}
    """
    try:
        response = requests.post(API_URL, headers=HEADERS, json={"query": mutation})
        if response.status_code == 200:
            log("info", f"Successfully updated variable: {name}", value=value)
        else:
            log("error", f"Failed to update variable: {name}", status_code=response.status_code, response=response.text)
    except Exception as e:
        log("error", f"Error during variable upsert: {e}")


def token_operations():
    """Handles token refresh and upsert operations."""
    try:
        refresh = os.getenv("REFRESH")
        token = os.getenv("TOKEN")

        if refresh is None or token is None:
            log("error", "Environment variables 'REFRESH' or 'TOKEN' are not set.")
            exit(1)

        refresh = int(refresh)
        token = int(token)

        # Update values
        new_token = token + refresh
        new_refresh = refresh + 1

        # Upsert values to Railway
        upsert_variable("token", new_token)
        upsert_variable("refresh", new_refresh)

        log("info", "Token operations completed", new_token=new_token, new_refresh=new_refresh)
    except Exception as e:
        log("error", f"Error in token_operations: {e}")


# Main Script
if __name__ == "__main__":
    log("info", "Starting script")
    validate_environment()

    if ENABLE_LOOP:
        log("info", "Loop enabled. Scheduler starting.")
        scheduler = BackgroundScheduler()
        scheduler.add_job(token_operations, "interval", seconds=30)
        scheduler.start()

        try:
            while True:
                pass  # Infinite loop to keep the script alive for Railway
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            log("info", "Scheduler stopped.")
    else:
        log("info", "Loop disabled. Running token operations once.")
        token_operations()
