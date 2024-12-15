from flask import Flask, jsonify, request
import time
import asyncio
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"okokok": "trainyuh🚅"})


@app.route('/firstTest', methods=['POST'])
def test():
    data = request.json
    return jsonify({"the data": deez, "also": data})


PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
ENVIRONMENT_ID = os.getenv("RAILWAY_ENVIRONMENT_ID")
SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
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
        print('error')

        
async def resetKeys():
    error = False
    while not error:
        try:
            token = os.getenv("token")
            refresh = os.getenv("refresh")
            print(f"token: {token}\nrefresh: {refresh}")
            new_token = token + refresh
            new_refresh = reftesh + 1
            upsert_variable("refresh", new_refresh)
            upsert_variable("token", new_token)
            time.sleep(30)
        except Exception as e:
            #handle errors
            error = True
        

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
    resetKeys()
