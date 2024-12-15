from flask import Flask, jsonify, request
import time
import asyncio
import os
import requests  # Import missing requests module

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"okokok": "trainyuh🚅"})


@app.route('/firstTest', methods=['POST'])
def test():
    data = request.json
    return jsonify({"also": data})  # Removed undefined variable 'deez'


# Environment variables
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


async def resetKeys():
    error = False
    while not error:
        try:
            token = os.getenv("token")
            refresh = int(os.getenv("refresh", 0))  # Ensure refresh is treated as an integer
            print(f"token: {token}\nrefresh: {refresh}")
            new_token = f"{token}{refresh}"
            new_refresh = refresh + 1
            upsert_variable("refresh", new_refresh)
            upsert_variable("token", new_token)
            await asyncio.sleep(30)  # Use asyncio.sleep for non-blocking sleep
        except Exception as e:
            print(f"Error in resetKeys: {e}")
            error = True


if __name__ == '__main__':
    # Start the Flask app
    app.run(debug=True, port=os.getenv("PORT", default=5000))
    
    # Run resetKeys asynchronously
    asyncio.run(resetKeys())
