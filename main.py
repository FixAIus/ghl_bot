import os
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler

# Toggle this to enable/disable the loop
ENABLE_LOOP = True

# Environment Variables
RW_PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
RW_ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
RW_API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")

RW_HEADERS = {
    "Authorization": f"Bearer {RW_API_TOKEN}",
    "Content-Type": "application/json",
}

# Constants
GHL_URL = "https://services.leadconnectorhq.com/oauth/token"
RW_API_URL = "https://backboard.railway.app/graphql/v2"


# Utility Functions
def log(level, msg, **kwargs):
    print(json.dumps({"level": level, "msg": msg, **kwargs}))


def validate_environment():
    """Validates the required environment variables."""
    if not all([RW_PROJECT_ID, RW_ENVIRONMENT_ID, RW_API_TOKEN, GHL_CLIENT_ID, GHL_CLIENT_SECRET]):
        log("error", "Missing required environment variables.")
        exit(1)


def fetch_variables():
    """Fetches current GHL_ACCESS and GHL_REFRESH values from the Railway API."""
    query = f"""
    query {{
      variables(
        projectId: "{RW_PROJECT_ID}"
        environmentId: "{RW_ENVIRONMENT_ID}"
      )
    }}
    """
    try:
        response = requests.post(RW_API_URL, headers=RW_HEADERS, json={"query": query})
        log(
            "info" if response.status_code == 200 else "error",
            "#1 Fetch RW Environment Variables",
            status_code=response.status_code,
            response_text=response.text,
        )
        if response.status_code == 200:
            variables = response.json().get("data", {}).get("variables", {})
            return {
                "GHL_ACCESS": variables.get("GHL_ACCESS"),
                "GHL_REFRESH": variables.get("GHL_REFRESH"),
            }
        return None
    except Exception as e:
        log("error", "Error during fetch_variables", error=str(e))
        return None


def upsert_variable(name, value):
    """Upserts a variable in Railway."""
    mutation = f"""
    mutation {{
      variableUpsert(
        input: {{
          projectId: "{RW_PROJECT_ID}"
          environmentId: "{RW_ENVIRONMENT_ID}"
          name: "{name}"
          value: "{value}"
        }}
      )
    }}
    """
    try:
        response = requests.post(RW_API_URL, headers=RW_HEADERS, json={"query": mutation})
        log(
            "info" if response.status_code == 200 else "error",
            f"#3 Upsert {name} to RW Environment",
            value=value,
            status_code=response.status_code,
            response_text=response.text,
        )
    except Exception as e:
        log("error", f"Error during variable upsert: {name}", error=str(e))


def refresh_tokens(old_access, old_refresh):
    """Refreshes GHL tokens using the provided refresh token."""
    ghl_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Bearer {old_access}",
    }
    ghl_payload = {
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": old_refresh,
        "user_type": "Company",
    }

    try:
        response = requests.post(GHL_URL, data=ghl_payload, headers=ghl_headers)
        log(
            "info" if response.status_code == 200 else "error",
            "#2 Refresh GHL Tokens",
            status_code=response.status_code,
            response_text=response.text,
        )
        if response.status_code == 200:
            new_access_token = response.json().get("access_token")
            new_refresh_token = response.json().get("refresh_token")
            return new_access_token, new_refresh_token
        return None, None
    except Exception as e:
        log("error", "Error during token refresh", error=str(e))
        return None, None


def token_operations():
    """Handles token refresh and upsert operations."""
    try:
        variables = fetch_variables()
        if not variables:
            log("error", "Unable to load variables from API.")
            return

        old_access = variables.get("GHL_ACCESS")
        old_refresh = variables.get("GHL_REFRESH")

        if not old_access or not old_refresh:
            log("error", "Missing 'GHL_ACCESS' or 'GHL_REFRESH' values.")
            return

        # Log loaded values
        log("info", "#1 <Loaded token values>", GHL_ACCESS=old_access, GHL_REFRESH=old_refresh)

        # Refresh tokens using the GHL API
        new_access, new_refresh = refresh_tokens(old_access, old_refresh)
        if not new_access or not new_refresh:
            log("error", "Token refresh failed. Skipping upsert.")
            return

        # Upsert updated values to Railway
        upsert_variable("GHL_ACCESS", new_access)
        upsert_variable("GHL_REFRESH", new_refresh)

    except ValueError as ve:
        log("error", "Variable parsing error", error=str(ve))
    except Exception as e:
        log("error", "Error in token_operations", error=str(e))


# Main Script
if __name__ == "__main__":
    log("info", "Starting script")
    validate_environment()

    if ENABLE_LOOP:
        log("info", "Loop enabled. Scheduler starting.")
        scheduler = BackgroundScheduler()
        scheduler.add_job(token_operations, "interval", hours=23.5)
        scheduler.start()

        try:
            while True:
                pass  # Infinite loop to keep the script alive for Railway
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            log("info", "Scheduler stopped.")
    else:
        log("info", "Loop disabled. Displaying current token values only.")
        variables = fetch_variables()
        if variables:
            log("info", "Current token values", GHL_ACCESS=variables.get("GHL_ACCESS"), GHL_REFRESH=variables.get("GHL_REFRESH"))
        else:
            log("error", "Unable to fetch token values.")
