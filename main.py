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


def upsert_variable(name, value):
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


        
async def resetKeys():
    error = False
    while(!error):
        try:
            token = os.getenv("token")
            refresh = os.getenv("refresh")
            new_token = token + refresh
            new_refresh = reftesh + 1
            upsert_variable("refresh", new_refresh)
            upsert_variable("token", new_token)
        except Exception e:
            #handle errors
            error = True
        

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
    resetKeys()
