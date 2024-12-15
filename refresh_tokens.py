import os
import time
import requests

# Load environment variables
PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
API_TOKEN = "2f713959-4bce-49e6-ab6b-c1183b86f026"
API_URL = "https://backboard.railway.com/graphql/v2"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

def upsert_variable(name, value):
    """Upserts a variable into Railway."""
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
        if response.status_code != 200:
            print(f"Failed to upsert variable: {name}. Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error in upsert_variable: {e}")

def load_current_tokens():
    """Loads current token values from environment variables."""
    refresh = int(os.getenv("refresh"))
    token = int(os.getenv("token"))
    return {"refresh": refresh, "token": token}

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

            print(f"Current refresh: {refresh_value}, Current token: {token_value}")

            # Update token and refresh values
            new_token_value = token_value + refresh_value
            new_refresh_value = refresh_value + 1

            # Upsert the new values
            upsert_variable("refresh", new_refresh_value)
            upsert_variable("token", new_token_value)

            print(f"Updated refresh: {new_refresh_value}, Updated token: {new_token_value}")

        except Exception as e:
            print(f"Error in refresh loop: {e}")

        # Wait for the interval before repeating
        time.sleep(interval)
