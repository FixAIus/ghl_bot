import os
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask, jsonify
import os

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


# Step 1: Load environment variables and log project info
PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
API_URL = "https://backboard.railway.com/graphql/v2"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

# Log project info loaded
print(json.dumps({"msg": "Project info loaded", "level": "info"}))


# Step 2: Define the `upsert_variable` function
def upsert_variable(name, value):
    """Upserts a variable into Railway."""
    print(json.dumps({"msg": "Upsert Variables Defined", "level": "info"}))  # Log function definition

    try:
        print(json.dumps({"msg": f"Function started for {name}", "level": "info"}))  # Log function start

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
            print(json.dumps({"msg": f"Updated {name} successfully", "level": "info", "value": value}))
        else:
            print(json.dumps({
                "msg": f"Failed to update {name}",
                "level": "error",
                "status_code": response.status_code,
                "response_text": response.text,
            }))
    except Exception as e:
        print(json.dumps({"msg": f"Error in upsert_variable: {e}", "level": "error"}))


# Step 3: Define the `token_operations` function
def token_operations():
    """
    Performs token operations: loads, increments, and upserts token values.
    """
    try:
        refresh = int(os.getenv("REFRESH", 0))
        token = int(os.getenv("TOKEN", 0))

        # Log the loaded token and refresh values
        print(json.dumps({"msg": "Operations started", "level": "info", "token": token, "refresh": refresh}))

        # Perform token updates
        new_token = token + refresh
        new_refresh = refresh + 1

        # Upsert new values
        upsert_variable("token", new_token)
        upsert_variable("refresh", new_refresh)

        # Log success
        print(json.dumps({
            "msg": "Token operations completed",
            "level": "info",
            "new_token": new_token,
            "new_refresh": new_refresh,
        }))
    except Exception as e:
        print(json.dumps({"msg": f"Error in token_operations: {e}", "level": "error"}))


# Step 4: Run `token_operations` every 30 seconds using APScheduler
if __name__ == "__main__":
    print(json.dumps({"msg": "Scheduler starting", "level": "info"}))  # Log scheduler start

    scheduler = BackgroundScheduler()
    scheduler.add_job(token_operations, "interval", seconds=30)
    scheduler.start()

    # Keep the script running
    try:
        while True:
            pass  # Infinite loop to keep the script alive for the scheduler
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
