import os
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler


# Helper function for logging
def log(message, level="info", **kwargs):
    """Centralized logging with JSON format."""
    log_entry = {"msg": message, "level": level}
    log_entry.update(kwargs)
    print(json.dumps(log_entry))


# Step 1: Load and validate environment variables
def load_env_vars():
    """Load required environment variables and validate them."""
    required_vars = ["RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID", "RAILWAY_SERVICE_ID", "RAILWAY_API_TOKEN"]
    env_vars = {var: os.getenv(var) for var in required_vars}

    missing_vars = [var for var, value in env_vars.items() if value is None]
    if missing_vars:
        log(f"Missing required environment variables: {', '.join(missing_vars)}", "error")
        exit(1)

    return {
        "PROJECT_ID": env_vars["RAILWAY_PROJECT_ID"],
        "ENVIRONMENT_ID": env_vars["RAILWAY_ENVIRONMENT_ID"],
        "SERVICE_ID": env_vars["RAILWAY_SERVICE_ID"],
        "API_URL": "https://backboard.railway.app/graphql/v2",
        "HEADERS": {
            "Authorization": f"Bearer {env_vars['RAILWAY_API_TOKEN']}",
            "Content-Type": "application/json",
        },
    }


# Step 2: Define the `upsert_variable` function
def upsert_variable(name, value, config):
    """Upserts a variable into Railway."""
    log(f"Upserting variable '{name}' with value '{value}'")

    mutation = f"""
    mutation {{
      variableUpsert(
        input: {{
          projectId: "{config['PROJECT_ID']}"
          environmentId: "{config['ENVIRONMENT_ID']}"
          serviceId: "{config['SERVICE_ID']}"
          name: "{name}"
          value: "{value}"
        }}
      )
    }}
    """
    try:
        response = requests.post(config["API_URL"], headers=config["HEADERS"], json={"query": mutation})
        if response.status_code == 200:
            log(f"Successfully updated '{name}'", "info", value=value)
        else:
            log(f"Failed to update '{name}'", "error", status_code=response.status_code, response_text=response.text)
    except Exception as e:
        log(f"Error during upsert of '{name}': {e}", "error")


# Step 3: Define the `token_operations` function
def token_operations(config):
    """Performs token operations: increments and upserts token values."""
    try:
        refresh = os.getenv("REFRESH")
        token = os.getenv("TOKEN")

        if refresh is None or token is None:
            log("Environment variables 'REFRESH' or 'TOKEN' are not set", "error")
            exit(1)

        refresh, token = int(refresh), int(token)
        new_token, new_refresh = token + refresh, refresh + 1

        upsert_variable("token", new_token, config)
        upsert_variable("refresh", new_refresh, config)

        log("Token operations completed", "info", new_token=new_token, new_refresh=new_refresh)
    except Exception as e:
        log(f"Error in token_operations: {e}", "error")


# Main script execution
if __name__ == "__main__":
    config = load_env_vars()
    log("Scheduler starting")

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: token_operations(config), "interval", seconds=30)
    scheduler.start()

    try:
        log("Script is running. Press Ctrl+C to stop.")
        scheduler._event.wait()  # Keeps the script running
    except (KeyboardInterrupt, SystemExit):
        log("Scheduler shutting down")
        scheduler.shutdown()
