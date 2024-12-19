import os
import requests
import json
import traceback

# Environment Variables
RW_PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
RW_ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
RW_API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")

def log(level, msg, **kwargs):
    """Centralized logging function for structured JSON logging."""
    print(json.dumps({"level": level, "msg": msg, **kwargs}))

def fetch_railway_variables():
    """Fetch current GHL tokens from Railway."""
    query = f"""
    query {{
      variables(
        projectId: "{RW_PROJECT_ID}"
        environmentId: "{RW_ENVIRONMENT_ID}"
      )
    }}
    """
    try:
        response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            headers={"Authorization": f"Bearer {RW_API_TOKEN}", "Content-Type": "application/json"},
            json={"query": query}
        )
        if response.status_code == 200:
            variables = response.json().get("data", {}).get("variables", {})
            return variables.get("GHL_ACCESS"), variables.get("GHL_REFRESH")
        log("error", "Failed to fetch variables", status_code=response.status_code, response_text=response.text)
    except Exception as e:
        log("error", "Error fetching variables", traceback=traceback.format_exc())
    return None, None

def refresh_ghl_tokens(old_access, old_refresh):
    """Refresh GHL tokens using the provided refresh token."""
    try:
        response = requests.post(
            "https://services.leadconnectorhq.com/oauth/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Bearer {old_access}"
            },
            data={
                "client_id": GHL_CLIENT_ID,
                "client_secret": GHL_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": old_refresh,
                "user_type": "Company"
            }
        )
        if response.status_code == 200:
            tokens = response.json()
            return tokens.get("access_token"), tokens.get("refresh_token")
        log("error", "Token refresh failed", status_code=response.status_code, response_text=response.text)
    except Exception as e:
        log("error", "Error refreshing tokens", traceback=traceback.format_exc())
    return None, None

def update_railway_variable(name, value):
    """Update a variable in Railway."""
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
        response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            headers={"Authorization": f"Bearer {RW_API_TOKEN}", "Content-Type": "application/json"},
            json={"query": mutation}
        )
        if response.status_code != 200:
            log("error", f"Failed to update variable: {name}", status_code=response.status_code, response_text=response.text)
    except Exception as e:
        log("error", f"Error updating variable: {name}", traceback=traceback.format_exc())

def main():
    if not all([RW_PROJECT_ID, RW_ENVIRONMENT_ID, RW_API_TOKEN, GHL_CLIENT_ID, GHL_CLIENT_SECRET]):
        log("error", "Missing required environment variables")
        return

    log("info", "Starting token refresh")

    old_access, old_refresh = fetch_railway_variables()
    if not old_access or not old_refresh:
        log("error", "Failed to fetch current tokens")
        return

    new_access, new_refresh = refresh_ghl_tokens(old_access, old_refresh)
    if not new_access or not new_refresh:
        log("error", "Failed to refresh tokens")
        return

    update_railway_variable("GHL_ACCESS", new_access)
    update_railway_variable("GHL_REFRESH", new_refresh)

    log(
        "info", 
        "Tokens successfully updated", 
        old_tokens={"GHL_ACCESS": old_access, "GHL_REFRESH": old_refresh}, 
        new_tokens={"GHL_ACCESS": new_access, "GHL_REFRESH": new_refresh}
    )

if __name__ == "__main__":
    main()
