import os
import requests
import json
from flask import Flask, jsonify, request
import os

app = Flask(__name__)


def log(level, msg, **kwargs):
    """Centralized logger for structured JSON logging."""
    print(json.dumps({"level": level, "msg": msg, **kwargs}))


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route('/moveConvoForward', methods=['POST'])
def move_convo_forward():
    try:
        ##### Parse incoming data #####
        data = request.json
        required_fields = ["thread_id", "assistant_id", "ghl_contact_id", "ghl_recent_message"]
        
        # Check for missing fields
        received_fields = {field: data.get(field) for field in required_fields if field in data}
        if not all(field in data and data[field] for field in required_fields):
            log("error", "Missing required fields", received_fields=received_fields)
            return jsonify({"error": "Missing required fields"}), 400

        thread_id = data["thread_id"]
        assistant_id = data["assistant_id"]
        ghl_contact_id = data["ghl_contact_id"]
        ghl_recent_message = data["ghl_recent_message"]
        ghl_convo_id = data.get("ghl_convo_id")

        
        ##### Retrieve conversation ID if not provided #####
        if not ghl_convo_id or ghl_convo_id in ["", "null"]:
            search_response = requests.get(
                "https://services.leadconnectorhq.com/conversations/search",
                headers={
                    "Authorization": f"Bearer {GHL_TOKEN}",
                    "Version": "2021-04-15",
                    "Accept": "application/json"
                },
                params={"locationId": GHL_LOCATION_ID, "contactId": ghl_contact_id}
            )
            if search_response.status_code != 200:
                log("error", "Failed to retrieve conversation ID", 
                    status_code=search_response.status_code,
                    response=search_response.text,
                    ghl_contact_id=ghl_contact_id)
                return jsonify({"error": "Failed to retrieve conversation ID"}), 500

            ghl_convo_id = search_response.json().get("conversations", [{}])[0].get("id")
            if not ghl_convo_id:
                log("error", "No conversation ID found", 
                    ghl_contact_id=ghl_contact_id,
                    response=search_response.json())
                return jsonify({"error": "No conversation ID found"}), 404

            log("info", "Successfully retrieved conversation ID", 
                ghl_contact_id=ghl_contact_id,
                ghl_convo_id=ghl_convo_id)

        # Log successful field parsing after having conversation ID
        log("info", "Successfully parsed all required fields", 
            thread_id=thread_id,
            assistant_id=assistant_id,
            ghl_contact_id=ghl_contact_id,
            ghl_convo_id=ghl_convo_id)

        
        ##### Retrieve messages #####
        messages_response = requests.get(
            f"https://services.leadconnectorhq.com/conversations/{ghl_convo_id}/messages",
            headers={
                "Authorization": f"Bearer {GHL_TOKEN}",
                "Version": "2021-04-15",
                "Accept": "application/json"
            }
        )
        if messages_response.status_code != 200:
            log("error", "Failed to retrieve messages", 
                status_code=messages_response.status_code,
                response=messages_response.text,
                ghl_convo_id=ghl_convo_id)
            return jsonify({"error": "Failed to retrieve messages"}), 500

        all_messages = messages_response.json().get("messages", {}).get("messages", [])
        if not all_messages:
            log("error", "No messages found", 
                ghl_convo_id=ghl_convo_id,
                ghl_recent_message=ghl_recent_message)
            return jsonify({"error": "No messages found"}), 404

        log("info", "Successfully retrieved messages", 
            message_count=len(all_messages),
            ghl_recent_message=ghl_recent_message)

        
        ##### Compile new messages #####
        new_messages = [
            {"role": "user", "content": msg["body"]}
            for msg in all_messages if msg["direction"] == "inbound"
        ]
        if ghl_recent_message in [msg["body"] for msg in all_messages]:
            new_messages = new_messages[:[msg["body"] for msg in all_messages].index(ghl_recent_message) + 1]

        if not new_messages:
            log("info", "No new messages to process", 
                ghl_recent_message=ghl_recent_message)
            return jsonify({"error": "No new messages to process"}), 200

        log("info", "Successfully compiled messages", 
            message_count=len(new_messages),
            compiled_messages=new_messages)

        
        ##### Run thread and process responses #####
        
        ### Run
        run_response = openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
            additional_messages=new_messages
        )
        run_status, run_id = run_response.status, run_response.id
        
        log("info", "Thread run completed", 
            run_status=run_status,
            run_id=run_id,
            thread_id=thread_id)

        ### Process responses
        # Message
        if run_status == "completed":
            ai_messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run_id).data
            if not ai_messages:
                log("error", "No AI messages found",
                    run_id=run_id,
                    thread_id=thread_id)
                return jsonify({"error": "No AI messages found"}), 404

            ai_content = ai_messages[-1].content[0].text.value
            if "【" in ai_content and "】" in ai_content:
                ai_content = ai_content[:ai_content.find("【")] + ai_content[ai_content.find("】") + 1:]
            
            log("info", "Successfully processed AI response",
                run_id=run_id,
                thread_id=thread_id,
                ai_message=ai_content)
            return jsonify({"ai_response": ai_content, "ghl_convo_id": ghl_convo_id}), 200

        # Function
        elif run_status == "requires_action":
            tool_call = run_response.required_action.submit_tool_outputs.tool_calls[0]
            openai_client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=[{"tool_call_id": tool_call.id, "output": "success"}]
            )
            function_map = {"handoff": "handoff", "endConvo": "forced", "checkTier": "tier 1"}
            
            log("info", "Successfully processed function call",
                tool_call_id=tool_call.id,
                run_id=run_id,
                thread_id=thread_id,
                function_name=tool_call.function.name)
            return jsonify({
                "ghl_convo_id": ghl_convo_id,
                "stop": function_map.get(tool_call.function.name, f"Unexpected function '{tool_call.function.name}'")
            }), 200

        elif run_status in ["cancelling", "cancelled", "failed", "incomplete", "expired"]:
            log("error", "Run ended with non-success status",
                run_status=run_status,
                run_id=run_id,
                thread_id=thread_id)
            return jsonify({"stop": True, "technical_bug": run_status}), 200

        log("error", "Unhandled run status",
            run_status=run_status,
            run_id=run_id,
            thread_id=thread_id)
        return jsonify({"error": "Unhandled run status"}), 500

    except Exception as e:
        log("error", "Unhandled exception",
            error=str(e),
            traceback=traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# Demo format so GHL knows what response could contain
@app.route('/testEndpoint', methods=['POST'])
def possibleFormat():
    data = request.json
    log("info", "Received request parameters", **{
        k: data.get(k) for k in [
            "thread_id", "assistant_id", "ghl_contact_id", 
            "ghl_recent_message", "ghl_convo_id"
        ]
    })
    return jsonify({
        "stop": "handoff",
        "technical_bug": "run_status",
        "ai_response": "This is a test response",
        "ghl_convo_id": "test_convo_id",
        "error": "test error"
    })


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
