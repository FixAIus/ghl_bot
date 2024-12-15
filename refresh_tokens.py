import os
import time
import requests
import json

# Load environment variables
PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
API_URL = "https://backboard.railway.com/graphql/v2"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

def log(message, level="info", **kwargs):
    """
    Logs a structured message to Railway logs in JSON format.
    """
    log_entry = {"msg": message, "level": level}
    log_entry.update(kwargs)
    print(json.dumps(log_entry))

def upsert_variable(name, value):
    """
    Upserts a variable into Railway.
    """
    try:
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
        response = requests.post(API_URL, headers=HEADERS, json={"query": mutation})
        if response.status_code == 200:
            log(f"Successfully upserted variable: {name}", level="info", variable=name, value=value)
        else:
            log(
                f"Failed to upsert variable: {name}",
                level="error",
                status_code=response.status_code,
                response_text=response.text,
            )
    except Exception as e:
        log(f"Error in upsert_variable: {e}", level="error", variable=name)

def load_current_tokens():
    """
    Loads current token values from environment variables.
    """
    try:
        refresh = int(os.getenv("REFRESH", 0))
        token = int(os.getenv("TOKEN", 0))
        log("Loaded token values from environment", level="debug", refresh=refresh, token=token)
        return {"refresh": refresh, "token": token}
    except Exception as e:
        log(f"Error loading token values: {e}", level="error")
        return {"refresh": 0, "token": 0}

def refresh_tokens(interval=30):
    """
    Continuously refreshes tokens by adding 'refresh' to 'token',
    incrementing 'refresh', and upserting the updated values.
    """
    while True:
        try:
            # Load current values
            variables = load_current_tokens()
            refresh_value = variables["refresh"]
            token_value = variables["token"]

            log("Refreshing tokens", level="info", refresh=refresh_value, token=token_value)

            # Update token and refresh values
            new_token_value = token_value + refresh_value
            new_refresh_value = refresh_value + 1

            # Upsert the new values
            upsert_variable("refresh", new_refresh_value)
            upsert_variable("token", new_token_value)

            log(
                "Tokens refreshed successfully",
                level="info",
                new_refresh=new_refresh_value,
                new_token=new_token_value,
            )

        except Exception as e:
            log(f"Error in refresh loop: {e}", level="error")

        # Wait for the interval before repeating
        time.sleep(interval)
