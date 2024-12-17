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



# Helper Function 1: get_conversation_id
def get_conversation_id(ghl_contact_id):
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
        log("error", f"CONVO ID -- API call failed -- {ghl_contact_id}", 
            scope="Convo ID", status_code=search_response.status_code, 
            response=search_response.text, ghl_contact_id=ghl_contact_id)
        return None

    ghl_convo_id = search_response.json().get("conversations", [{}])[0].get("id")
    if not ghl_convo_id:
        log("error", f"CONVO ID -- No ID found -- {ghl_contact_id}", 
            scope="Convo ID", response=search_response.text, ghl_contact_id=ghl_contact_id)
        return None
    return ghl_convo_id


# Helper Function 2: retrieve_and_compile_messages
def retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message):
    messages_response = requests.get(
        f"https://services.leadconnectorhq.com/conversations/{ghl_convo_id}/messages",
        headers={
            "Authorization": f"Bearer {os.getenv('GHL_ACCESS')}",
            "Version": "2021-04-15",
            "Accept": "application/json"
        }
    )
    if messages_response.status_code != 200:
        log("error", f"GET MESSAGES -- API Call Failed -- {ghl_contact_id}", 
            scope="Get Messages", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id,
            status_code=messages_response.status_code, response=messages_response.text)
        return []

    all_messages = messages_response.json().get("messages", {}).get("messages", [])
    if not all_messages:
        log("error", f"GET MESSAGES -- No messages found -- {ghl_contact_id}", 
            scope="Get Messages", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)
        return []

    # Compile new messages
    new_messages = []
    for msg in all_messages:
        if msg["direction"] == "inbound":
            new_messages.insert(0, {"role": "user", "content": msg["body"]})
        if msg["body"] == ghl_recent_message:
            break

    if not new_messages:
        log("info", f"GET MESSAGES -- No new messages after filtering -- {ghl_contact_id}", 
            scope="Get Messages", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)
    return new_messages[::-1]


# Helper Function 3: process_message_response
def process_message_response(thread_id, run_id):
    ai_messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run_id).data
    if not ai_messages:
        log("error", f"AI MESSAGE -- No messages found after run completion -- {thread_id}", 
            scope="AI Message", run_id=run_id, thread_id=thread_id, ghl_convo_id=thread_id)
        return None

    ai_content = ai_messages[-1].content[0].text.value
    if "【" in ai_content and "】" in ai_content:
        ai_content = ai_content[:ai_content.find("【")] + ai_content[ai_content.find("】") + 1:]
    return ai_content


# Helper Function 4: process_function_response
def process_function_response(thread_id, run_id, run_response):
    tool_call = run_response.required_action.submit_tool_outputs.tool_calls[0]
    openai_client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=[{"tool_call_id": tool_call.id, "output": "success"}]
    )
    function_map = {"handoff": "handoff", "endConvo": "forced", "checkTier": "tier 1"}
    log("info", f"AI FUNCTION -- Processed function call -- {thread_id}", 
        scope="AI Function", tool_call_id=tool_call.id, 
        run_id=run_id, function_name=tool_call.function.name, ghl_convo_id=thread_id)
    return function_map.get(tool_call.function.name, "Unexpected function")



# Main Function: move_convo_forward
@app.route('/moveConvoForward', methods=['POST'])
def move_convo_forward():
    try:
        # Parse incoming data
        data = request.json
        required_fields = ["thread_id", "assistant_id", "ghl_contact_id", "ghl_recent_message"]
        if not all(field in data and data[field] for field in required_fields):
            log("error", f"GENERAL -- Missing required fields -- {ghl_contact_id}", 
                scope="General", received_fields=data, ghl_contact_id=ghl_contact_id)
            return jsonify({"error": "Missing required fields"}), 400

        thread_id = data["thread_id"]
        assistant_id = data["assistant_id"]
        ghl_contact_id = data["ghl_contact_id"]
        ghl_recent_message = data["ghl_recent_message"]
        ghl_convo_id = data.get("ghl_convo_id")

        log("info", f"GENERAL -- Parsed incoming request -- {ghl_contact_id}", 
            scope="General", thread_id=thread_id, assistant_id=assistant_id, ghl_contact_id=ghl_contact_id)

        # Retrieve conversation ID if not provided
        if not ghl_convo_id or ghl_convo_id in ["", "null"]:
            ghl_convo_id = get_conversation_id(ghl_contact_id)
            if not ghl_convo_id:
                return jsonify({"error": "Failed to retrieve conversation ID"}), 500
        log("info", f"CONVO ID -- Successfully retrieved conversation ID -- {ghl_contact_id}", 
            scope="Convo ID", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)

        # Retrieve and compile messages
        new_messages = retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message)
        if not new_messages:
            return jsonify({"error": "No new messages to process"}), 200
        log("info", f"GET MESSAGES -- Successfully compiled -- {ghl_contact_id}", 
            scope="Get Messages", message=new_messages, ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)

        # Run AI Thread
        run_response = openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread_id, assistant_id=assistant_id, additional_messages=new_messages
        )
        run_status, run_id = run_response.status, run_response.id
        log("info", f"AI RUN -- Thread run completed -- {ghl_contact_id}", 
            scope="AI Run", run_status=run_status, run_id=run_id, thread_id=thread_id, ghl_contact_id=ghl_contact_id)

        # Process run response
        if run_status == "completed":
            ai_content = process_message_response(thread_id, run_id)
            if ai_content:
                log("info", f"AI MESSAGE -- Successfully retrieved AI response -- {ghl_contact_id}", 
                    scope="AI Message", run_id=run_id, thread_id=thread_id, ai_message=ai_content, ghl_contact_id=ghl_contact_id)
                return jsonify({"ai_response": ai_content, "ghl_convo_id": ghl_convo_id}), 200
            log("error", f"AI MESSAGE -- No AI messages found -- {ghl_contact_id}", 
                scope="AI Message", run_id=run_id, thread_id=thread_id, ghl_contact_id=ghl_contact_id)
            return jsonify({"error": "No AI messages found"}), 404

        elif run_status == "requires_action":
            stop_reason = process_function_response(thread_id, run_id, run_response)
            log("info", f"AI FUNCTION -- Processed function call -- {ghl_contact_id}", 
                scope="AI Function", run_id=run_id, thread_id=thread_id, stop_reason=stop_reason, ghl_contact_id=ghl_contact_id)
            return jsonify({"ghl_convo_id": ghl_convo_id, "stop": stop_reason}), 200

        log("error", f"AI RUN -- Run ended with non-success status -- {ghl_contact_id}", 
            scope="AI Run", run_status=run_status, run_id=run_id, thread_id=thread_id, ghl_contact_id=ghl_contact_id)
        return jsonify({"stop": True, "technical_bug": run_status}), 200

    except Exception as e:
        log("error", "GENERAL -- Unhandled exception occurred", 
            scope="General", error=str(e))
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
