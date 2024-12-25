from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from threading import Timer

app = Flask(__name__)

# Store active timers for users
user_timers = {}

# Function to handle timer expiration
def timer_expired(user):
    if user in user_timers:
        del user_timers[user]

@app.route('/timer', methods=['POST'])
def manage_timer():
    user = request.json.get('user')
    if not user:
        return jsonify({"error": "User parameter is required."}), 400

    current_time = datetime.now()

    if user in user_timers:
        timer_info = user_timers[user]
        timer_info['timer'].cancel()
        new_timer = Timer(30, timer_expired, [user])
        new_timer.start()
        new_end_time = current_time + timedelta(seconds=30)
        user_timers[user] = {
            'end_time': new_end_time,
            'timer': new_timer
        }
        return jsonify({"message": f"Timer for {user} reset to end at {new_end_time}."})
    else:
        # Create a new timer
        new_timer = Timer(30, timer_expired, [user])
        new_timer.start()
        new_end_time = current_time + timedelta(seconds=30)
        user_timers[user] = {
            'end_time': new_end_time,
            'timer': new_timer
        }
        return jsonify({"message": f"30 second timer started for user: {user} to end at {new_end_time}."})






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
