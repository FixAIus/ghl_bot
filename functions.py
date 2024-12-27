import os
import requests
import json
from openai import OpenAI


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def fetch_ghl_access_token():
    """Fetch current GHL access token from Railway."""
    query = f"""
    query {{
      variables(
        projectId: "{os.getenv('RAILWAY_PROJECT_ID')}"
        environmentId: "{os.getenv('RAILWAY_ENVIRONMENT_ID')}"
        serviceId: "{os.getenv('RAILWAY_SERVICE_ID')}"
      )
    }}
    """
    try:
        response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": f"Bearer {os.getenv('RW_API_TOKEN')}", 
                "Content-Type": "application/json"
            },
            json={"query": query}
        )
        if response.status_code == 200:
            token = response.json().get("data", {}).get("variables", {}).get("GHL_ACCESS")
            if token:
                return token
        log("error", f"GHL Access -- Fetch token API failed", 
            scope="GHL Access", status_code=response.status_code, 
            response=response.text)
    except Exception as e:
        log("error", f"GHL Access -- Fetch token code error", 
            scope="GHL Access", error=str(e))
    return None


class GHLResponseObject:
    def __init__(self):
        """Initialize empty response schema."""
        self.schema = {
            "response_type": None,
            "action": None,
            "message": None
        }
    
    def add_message(self, message):
        """
        Args:
            message (str): Message content to add
        """
        self.schema["message"] = message
        if self.schema["response_type"] == "action":
            self.schema["response_type"] = "message_action"
        elif not self.schema["response_type"]:
            self.schema["response_type"] = "message"
    
    def add_action(self, action_type, details=None):
        """
        Args:
            action_type (str): Type of action ('force end', 'handoff', 'add_contact_id', etc.)
            details (dict, optional): Additional action details
        """
        self.schema["action"] = {
            "type": action_type,
            "details": details or {}
        }
        if self.schema["response_type"] == "message":
            self.schema["response_type"] = "message_action"
        elif not self.schema["response_type"]:
            self.schema["response_type"] = "action"
    
    def get_response(self):
        """Return the final response schema, removing any None values."""
        return {k: v for k, v in self.schema.items() if v is not None}


def log(level, msg, **kwargs):
    """Centralized logger for structured JSON logging."""
    print(json.dumps({"level": level, "msg": msg, **kwargs}))


def validate_request_data(data):
    """
    Validate request data, ensure required fields are present, and handle conversation ID retrieval.
    Returns validated fields dictionary or None if validation fails.
    """
    required_fields = ["thread_id", "assistant_id", "ghl_contact_id", "ghl_recent_message"]
    fields = {field: data.get(field) for field in required_fields}
    fields["ghl_convo_id"] = data.get("ghl_convo_id")
    fields["add_convo_id_action"] = False  # Track if convo ID was added dynamically

    missing_fields = [field for field in required_fields if not fields[field] or fields[field] in ["", "null", None]]
    if missing_fields:
        log("error", f"Validation -- Missing {', '.join(missing_fields)} -- {fields['ghl_contact_id']}",
            ghl_contact_id=fields["ghl_contact_id"], scope="Validation", received_fields=fields)
        return None

    if not fields["ghl_convo_id"] or fields["ghl_convo_id"] in ["", "null"]:
        fields["ghl_convo_id"] = get_conversation_id(fields["ghl_contact_id"])
        if not fields["ghl_convo_id"]:
            return None
        fields["add_convo_id_action"] = True  # Signal action to add convo ID to response

    log("info", f"Validation -- Fields Received -- {fields['ghl_contact_id']}", scope="Validation", **fields)
    return fields


def get_conversation_id(ghl_contact_id):
    """Retrieve conversation ID from GHL API."""
    token = fetch_ghl_access_token()
    if not token:
        return None

    search_response = requests.get(
        "https://services.leadconnectorhq.com/conversations/search",
        headers={
            "Authorization": f"Bearer {token}",
            "Version": "2021-04-15",
            "Accept": "application/json"
        },
        params={"locationId": os.getenv('GHL_LOCATION_ID'), "contactId": ghl_contact_id}
    )
    
    if search_response.status_code != 200:
        log("error", f"Validation -- Get convo ID API call failed -- {ghl_contact_id}", 
            scope="Validation", status_code=search_response.status_code, 
            response=search_response.text, ghl_contact_id=ghl_contact_id)
        return None

    conversations = search_response.json().get("conversations", [])
    if not conversations:
        log("error", f"Validation -- No Convo ID found -- {ghl_contact_id}", 
            scope="Validation", response=search_response.text, ghl_contact_id=ghl_contact_id)
        return None
        
    return conversations[0].get("id")


def retrieve_and_compile_messages(ghl_convo_id, ghl_recent_message, ghl_contact_id):
    """Retrieve messages from GHL API and compile them for processing."""
    token = fetch_ghl_access_token()
    if not token:
        log("error", f"Compile Messages -- Token fetch failed -- {ghl_contact_id}", 
            scope="Compile Messages", ghl_contact_id=ghl_contact_id)
        return []

    messages_response = requests.get(
        f"https://services.leadconnectorhq.com/conversations/{ghl_convo_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Version": "2021-04-15",
            "Accept": "application/json"
        }
    )
    if messages_response.status_code != 200:
        log("error", f"Compile Messages -- API Call Failed -- {ghl_contact_id}", 
            scope="Compile Messages", ghl_contact_id=ghl_contact_id, ghl_convo_id=ghl_convo_id,
            ghl_recent_message=ghl_recent_message, status_code=messages_response.status_code, response=messages_response.text)
        return []

    all_messages = messages_response.json().get("messages", {}).get("messages", [])
    if not all_messages:
        log("error", f"Compile Messages -- No messages found -- {ghl_contact_id}", 
            scope="Compile Messages", ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id,
            ghl_recent_message=ghl_recent_message, api_response=messages_response.json())
        return []

    new_messages = []
    if any(msg["body"] == ghl_recent_message for msg in all_messages):
        for msg in all_messages:
            if msg["direction"] == "inbound":
                new_messages.insert(0, {"role": "user", "content": msg["body"]})
            if msg["body"] == ghl_recent_message:
                break
    else:
        new_messages.append({"role": "user", "content": ghl_recent_message})

    log("info", f"Compile Messages -- Successfully compiled -- {ghl_contact_id}", 
        scope="Compile Messages", messages=[msg["content"] for msg in new_messages[::-1]], api_response=messages_response.json(),
        ghl_convo_id=ghl_convo_id, ghl_contact_id=ghl_contact_id, ghl_recent_message=ghl_recent_message)
    return new_messages[::-1]


def run_ai_thread(thread_id, assistant_id, messages, ghl_contact_id):
    """Run AI thread and get initial response."""
    run_response = openai_client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
        additional_messages=messages
    )
    run_status, run_id = run_response.status, run_response.id    
    return run_response, run_status, run_id


def process_message_response(thread_id, run_id, ghl_contact_id):
    """Process completed message response from AI."""
    ai_messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run_id).data
    if not ai_messages:
        log("error", f"AI Message -- Get message failed -- {ghl_contact_id}", 
            scope="AI Message", run_id=run_id, thread_id=thread_id, 
            response=ai_messages, ghl_contact_id=ghl_contact_id)
        return None

    ai_content = ai_messages[-1].content[0].text.value
    if "【" in ai_content and "】" in ai_content:
        ai_content = ai_content[:ai_content.find("【")] + ai_content[ai_content.find("】") + 1:]
    
    log("info", f"AI Message -- Successfully retrieved AI response -- {ghl_contact_id}", 
        scope="AI Message", run_id=run_id, thread_id=thread_id, 
        ai_message=ai_content, ghl_contact_id=ghl_contact_id)
    return ai_content


def process_function_response(thread_id, run_id, run_response, ghl_contact_id):
    """Process function call response from AI."""
    tool_call = run_response.required_action.submit_tool_outputs.tool_calls[0]
    function_args = json.loads(tool_call.function.arguments)
    openai_client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=[{"tool_call_id": tool_call.id, "output": "success"}]
    )

    if "handoff" in function_args:
        action = "handoff"
    else:
        action = "stop"

    # Log the processed function call
    log("info", f"AI Function -- Processed function call -- {ghl_contact_id}", 
        scope="AI Function", tool_call_id=tool_call.id, run_id=run_id, 
        thread_id=thread_id, function=function_args, selected_action=action, 
        ghl_contact_id=ghl_contact_id)
    
    return action
