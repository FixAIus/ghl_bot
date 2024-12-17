import os
import requests
import json
from flask import Flask, jsonify, request
from openai import OpenAI


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)


# Centralized logging function
def log(level, msg, **kwargs):
    print(json.dumps({"level": level, "msg": msg, **kwargs}))



# Function 1: Retrieve conversation ID
def get_conversation_id(ghl_contact_id):
    """Fetch the conversation ID if not provided."""
    search_response = requests.get(
        "https://services.leadconnectorhq.com/conversations/search",
        headers={
            "Authorization": f"Bearer {os.getenv('GHL_ACCESS')}",
            "Version": "2021-04-15",
            "Accept": "application/json"
        },
        params={"locationId": os.getenv('GHL_LOCATION_ID'), "contactId": ghl_contact_id}
    )
    if search_response.status_code != 200:
        log("error", "Failed to retrieve conversation ID", 
            status_code=search_response.status_code,
            response=search_response.text,
            ghl_contact_id=ghl_contact_id)
        return None

    ghl_convo_id = search_response.json().get("conversations", [{}])[0].get("id")
    if not ghl_convo_id:
        log("error", "No conversation ID found", 
            ghl_contact_id=ghl_contact_id,
            response=search_response.json())
        return None
    
    log("info", "Successfully retrieved conversation ID", 
        ghl_contact_id=ghl_contact_id, ghl_convo_id=ghl_convo_id)
    return ghl_convo_id



# Function 2: Retrieve and compile new messages
def retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message):
    """Fetch messages and compile new ones based on ghl_recent_message."""
    messages_response = requests.get(
        f"https://services.leadconnectorhq.com/conversations/{ghl_convo_id}/messages",
        headers={
            "Authorization": f"Bearer {os.getenv('GHL_ACCESS')}",
            "Version": "2021-04-15",
            "Accept": "application/json"
        }
    )
    if messages_response.status_code != 200:
        log("error", "Failed to retrieve messages", 
            status_code=messages_response.status_code,
            response=messages_response.text,
            ghl_convo_id=ghl_convo_id)
        return []

    all_messages = messages_response.json().get("messages", {}).get("messages", [])
    if not all_messages:
        log("error", "No messages found", ghl_convo_id=ghl_convo_id)
        return []

    # Compile new messages
    new_messages = []
    for msg in all_messages:
        if msg["direction"] == "inbound":
            new_messages.insert(0, {"role": "user", "content": msg["body"]})
        if msg["body"] == ghl_recent_message:
            break

    if not new_messages:
        log("info", "No new messages to process", ghl_convo_id=ghl_convo_id)
        return []

    log("info", "Successfully compiled messages", message_count=len(new_messages))
    return new_messages[::-1]  # Reverse the order for OpenAI compatibility



# Function 3: Process a response that is a message
def process_message_response(thread_id, run_id):
    """Handle a completed run and process the AI message."""
    ai_messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run_id).data
    if not ai_messages:
        log("error", "No AI messages found", run_id=run_id, thread_id=thread_id)
        return None

    ai_content = ai_messages[-1].content[0].text.value
    if "【" in ai_content and "】" in ai_content:
        ai_content = ai_content[:ai_content.find("【")] + ai_content[ai_content.find("】") + 1:]

    log("info", "Successfully processed AI response", 
        run_id=run_id, thread_id=thread_id, ai_message=ai_content)
    return ai_content



# Function 4: Process a response that is a function call
def process_function_response(thread_id, run_id, run_response):
    """Handle a requires_action run and process the function call."""
    tool_call = run_response.required_action.submit_tool_outputs.tool_calls[0]
    openai_client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=[{"tool_call_id": tool_call.id, "output": "success"}]
    )
    function_map = {"handoff": "handoff", "endConvo": "forced", "checkTier": "tier 1"}

    log("info", "Successfully processed function call", 
        tool_call_id=tool_call.id, run_id=run_id, thread_id=thread_id, 
        function_name=tool_call.function.name)
    return function_map.get(tool_call.function.name, f"Unexpected function '{tool_call.function.name}'")



# Main Endpoint
@app.route('/moveConvoForward', methods=['POST'])
def move_convo_forward():
    try:
        # Parse incoming data
        data = request.json
        required_fields = ["thread_id", "assistant_id", "ghl_contact_id", "ghl_recent_message"]
        if not all(field in data and data[field] for field in required_fields):
            log("error", "Missing required fields", received_fields=data)
            return jsonify({"error": "Missing required fields"}), 400

        thread_id = data["thread_id"]
        assistant_id = data["assistant_id"]
        ghl_contact_id = data["ghl_contact_id"]
        ghl_recent_message = data["ghl_recent_message"]
        ghl_convo_id = data.get("ghl_convo_id")

        # Retrieve conversation ID if not provided
        if not ghl_convo_id or ghl_convo_id in ["", "null"]:
            ghl_convo_id = get_conversation_id(ghl_contact_id)
            if not ghl_convo_id:
                return jsonify({"error": "Failed to retrieve conversation ID"}), 500

        # Retrieve and compile messages
        new_messages = retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message)
        if not new_messages:
            return jsonify({"error": "No new messages to process"}), 200

        # Run AI Thread
        run_response = openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread_id, assistant_id=assistant_id, additional_messages=new_messages
        )
        run_status, run_id = run_response.status, run_response.id
        log("info", "Thread run completed", run_status=run_status, run_id=run_id, thread_id=thread_id)

        # Process run response
        if run_status == "completed":
            ai_content = process_message_response(thread_id, run_id)
            if ai_content:
                return jsonify({"ai_response": ai_content, "ghl_convo_id": ghl_convo_id}), 200
            return jsonify({"error": "No AI messages found"}), 404

        elif run_status == "requires_action":
            stop_reason = process_function_response(thread_id, run_id, run_response)
            return jsonify({"ghl_convo_id": ghl_convo_id, "stop": stop_reason}), 200

        log("error", "Run ended with non-success status", run_status=run_status)
        return jsonify({"stop": True, "technical_bug": run_status}), 200

    except Exception as e:
        log("error", "Unhandled exception", error=str(e))
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
