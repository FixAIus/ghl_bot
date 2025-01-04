import json
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from threading import Timer

app = Flask(__name__)

# Store active timers for users
user_timers = {}


# Function to handle timer expiration
# Literally just removes the user from user_timers
def timer_expired(user):
    if user in user_timers:
        del user_timers[user]
        log("INFO", f"Timer expired for user: {user}", state=user_timers)


# Centralized logger function
def log(level, msg, **kwargs):
    try:
        print(json.dumps({"level": level, "msg": f"{msg} --- {str(user_timers)}"}))
    except TypeError as e:
        print(json.dumps({"level": "ERROR", "msg": "Logging serialization error", "error": str(e)}))


# Trigger this endpoint to start a new user timer
@app.route('/timer', methods=['POST'])
def manage_timer():
    user = request.json.get('user')
    if not user:
        log("ERROR", "User parameter is missing in request.", state=user_timers)
        return jsonify({"error": "User parameter is required."}), 400

    current_time = datetime.now()

    # Resets timer if there is already an active user timer
    if user in user_timers:
        timer_info = user_timers[user]
        time_left = (timer_info['end_time'] - current_time).total_seconds()

        # Reset the timer
        timer_info['timer'].cancel()
        new_timer = Timer(30, timer_expired, [user])
        new_timer.start()
        user_timers[user] = {
            'end_time': current_time + timedelta(seconds=30),
            'timer': new_timer
        }
        log("INFO", f"Timer for {user} reset.", time_left=time_left, state=user_timers)
        return jsonify({"message": f"Timer for {user} reset at {time_left:.2f} seconds remaining."})

    # If no active timer, start a new one
    else:
        # Create a new timer
        new_timer = Timer(30, timer_expired, [user])
        new_timer.start()
        user_timers[user] = {
            'end_time': current_time + timedelta(seconds=30),
            'timer': new_timer
        }
        log("INFO", f"30 second timer started for user: {user}", state=user_timers)
        return jsonify({"message": f"30 second timer started for user: {user}"})






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
