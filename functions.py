import os
import requests
import json
from openai import OpenAI


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def log(level, msg, **kwargs):
    """Centralized logger for structured JSON logging."""
    print(json.dumps({"level": level, "msg": msg, **kwargs}))


def validate_request_data(data):
    """
    Validate request data, ensure required fields are present, and handle conversation ID retrieval.
    Returns validated fields dictionary or None if validation fails.
    """
    # Define and extract required fields
    required_fields = ["thread_id", "assistant_id", "ghl_contact_id", "ghl_recent_message"]
    fields = {field: data.get(field) for field in required_fields}
    fields["ghl_convo_id"] = data.get("ghl_convo_id")
    
    # Check for missing required fields (excluding ghl_convo_id)
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        log("error", f"GENERAL -- Missing {', '.join(missing_fields)}", 
            scope="General", received_fields=fields)
        return None
        
    # Try to get conversation ID if missing
    if not fields["ghl_convo_id"] or fields["ghl_convo_id"] in ["", "null"]:
        fields["ghl_convo_id"] = get_conversation_id(fields["ghl_contact_id"])
        if not fields["ghl_convo_id"]:
            log("error", "GENERAL -- Missing ghl_convo_id", 
                scope="General", received_fields=fields)
            return None

    log("info", "GENERAL -- Valid Request", **fields)
    return fields


def get_conversation_id(ghl_contact_id):
    """Retrieve conversation ID from GHL API."""
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
    
    #log("info", f"CONVO ID -- Successfully retrieved conversation ID -- {ghl_contact_id}", 
        #scope="Convo ID", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)
    return ghl_convo_id


def retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message, ghl_contact_id):
    """Retrieve messages from GHL API and compile them for processing."""
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

    new_messages = []
    for msg in all_messages:
        if msg["direction"] == "inbound":
            new_messages.insert(0, {"role": "user", "content": msg["body"]})
        if msg["body"] == ghl_recent_message:
            break

    if not new_messages:
        log("info", f"GET MESSAGES -- No new messages after filtering -- {ghl_contact_id}", 
            scope="Get Messages", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id)
        return []

    log("info", f"GET MESSAGES -- Successfully compiled -- {ghl_contact_id}", 
        scope="Get Messages", message=new_messages, ghl_convo_id=ghl_convo_id, 
        ghl_contact_id=ghl_contact_id)
    return new_messages[::-1]


def run_ai_thread(thread_id, assistant_id, messages, ghl_contact_id):
    """Run AI thread and get initial response."""
    run_response = openai_client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
        additional_messages=messages
    )
    run_status, run_id = run_response.status, run_response.id
    
    log("info", f"AI RUN -- Thread run completed -- {ghl_contact_id}", 
        scope="AI Run", run_status=run_status, run_id=run_id, 
        thread_id=thread_id, ghl_contact_id=ghl_contact_id)
    
    return run_response, run_status, run_id


def process_message_response(thread_id, run_id, ghl_contact_id):
    """Process completed message response from AI."""
    ai_messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run_id).data
    if not ai_messages:
        log("error", f"AI MESSAGE -- No messages found after run completion -- {ghl_contact_id}", 
            scope="AI Message", run_id=run_id, thread_id=thread_id, ghl_contact_id=ghl_contact_id)
        return None

    ai_content = ai_messages[-1].content[0].text.value
    if "【" in ai_content and "】" in ai_content:
        ai_content = ai_content[:ai_content.find("【")] + ai_content[ai_content.find("】") + 1:]
    
    log("info", f"AI MESSAGE -- Successfully retrieved AI response -- {ghl_contact_id}", 
        scope="AI Message", run_id=run_id, thread_id=thread_id, 
        ai_message=ai_content, ghl_contact_id=ghl_contact_id)
    return ai_content


def process_function_response(thread_id, run_id, run_response, ghl_contact_id):
    """Process function call response from AI."""
    tool_call = run_response.required_action.submit_tool_outputs.tool_calls[0]
    openai_client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=[{"tool_call_id": tool_call.id, "output": "success"}]
    )
    
    log("info", f"AI FUNCTION -- Processed function call -- {ghl_contact_id}", 
        scope="AI Function", tool_call_id=tool_call.id, run_id=run_id, 
        thread_id=thread_id, function=tool_call.function, ghl_contact_id=ghl_contact_id)
    
    return tool_call.function
  
