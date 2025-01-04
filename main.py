import json
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from redis import Redis

app = Flask(__name__)

# Redis setup with environment variable
redis_url = os.getenv('REDIS_URL')
redis_client = Redis.from_url(redis_url, decode_responses=True)

def log(level, msg, **kwargs):
    """Centralized logger for structured JSON logging."""
    kwargs['state'] = str(kwargs.get('state', {}))
    print(json.dumps({"level": level, "msg": msg, **kwargs}))

@app.route('/timer', methods=['POST'])
def manage_timer():
    user = request.json.get('user')
    if not user:
        log("ERROR", "User parameter is missing in request.")
        return jsonify({"error": "User parameter is required."}), 400

    params = request.json.get('params', {})
    key = f"timer:{user}"
    current_time = datetime.now()
    end_time = (current_time + timedelta(seconds=30)).isoformat()

    # Set or reset the timer in Redis
    redis_client.set(key, json.dumps({"end_time": end_time, "params": params}), ex=30)
    log("INFO", f"30 second timer started --- user: {user}", state={key: redis_client.get(key)})

    return jsonify({"message": f"30 second timer started --- user: {user}"})

@app.route('/expired', methods=['POST'])
def handle_expired():
    """Simulate handling of expired timer (e.g., triggered by a background task or keyspace notification)."""
    user = request.json.get('user')
    key = f"timer:{user}"
    if redis_client.exists(key):
        timer_data = json.loads(redis_client.get(key))
        log("INFO", f"Handling expiration for user: {user}", params=timer_data.get('params'))
        # Perform post-timer logic here
        redis_client.delete(key)
        return jsonify({"message": f"Timer for {user} expired and handled."})
    else:
        return jsonify({"error": "No active timer found for user."}), 404






@app.route('/testEndpoint', methods=['POST'])
def possibleFormat():
    data = request.json
    log("info", "Received request parameters", **{
        k: data.get(k) for k in [
            "thread_id", "assistant_id", "ghl_contact_id", 
            "ghl_recent_message", "ghl_convo_id"
        ]
    })
    return jsonify(
        {
            "response_type": "action, message, message_action",
            "action": {
                "type": "force end, handoff, add_contact_id",
                "details": {
                    "ghl_convo_id": "afdlja;ldf"
                }
            },
            "message": "wwwwww",
            "error": "booo error"
            
        }
    )



if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
