import os
import requests
import json

# Environment Variables
#RW_PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
#RW_ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
#RW_API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
#GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
#GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")

def log(level, msg, **kwargs):
    print(json.dumps({"level": level, "msg": msg, **kwargs}))

def fetch_railway_variables():
    """Fetches current GHL tokens from Railway."""
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
        log("error", "Failed to fetch variables", status_code=response.status_code)
        return None, None
    except Exception as e:
        log("error", "Error fetching variables", error=str(e))
        return None, None

def refresh_ghl_tokens(old_access, old_refresh):
    """Gets new GHL tokens using the refresh token."""
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
            data = response.json()
            return data.get("access_token"), data.get("refresh_token")
        log("error", "Token refresh failed", status_code=response.status_code)
        return None, None
    except Exception as e:
        log("error", "Error refreshing tokens", error=str(e))
        return None, None

def update_railway_variable(name, value):
    """Updates a variable in Railway."""
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
        log(
            "info" if response.status_code == 200 else "error",
            f"Variable update: {name}",
            status_code=response.status_code
        )
    except Exception as e:
        log("error", f"Error updating {name}", error=str(e))

def main():
    log('info', "wassgood 5 minutes mcnigga")

if __name__ == "__main__":
    main()
