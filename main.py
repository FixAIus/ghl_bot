import os
from flask import Flask, jsonify, request
import traceback
from functions import (
    log,
    GHLResponseObject,
    validate_request_data,
    get_conversation_id,
    retrieve_and_compile_messages,
    run_ai_thread,
    process_message_response,
    process_function_response
)

app = Flask(__name__)




@app.route('/moveConvoForward', methods=['POST'])
def move_convo_forward():
    """
    Main endpoint for handling conversation flow between user and AI assistant.
    Processes incoming messages and returns appropriate AI responses or function calls.
    """
    try:
        # Initialize response object
        res_obj = GHLResponseObject()

        # Validate request data and handle conversation ID
        validated_fields = validate_request_data(request.json)
        if not validated_fields:
            return jsonify({"error": "Invalid request data"}), 400

        ghl_convo_id = validated_fields["ghl_convo_id"]

        # If conversation ID was added during validation, include it in the response
        if validated_fields.get("add_convo_id_action"):
            res_obj.add_action("add_convo_id", {"ghl_convo_id": ghl_convo_id})

        # Retrieve and process messages
        new_messages = retrieve_and_compile_messages(
            ghl_convo_id,
            validated_fields["ghl_recent_message"],
            validated_fields["ghl_contact_id"]
        )
        if not new_messages:
            return jsonify({"error": "No messages added"}), 400

        # Run AI thread and get response
        run_response, run_status, run_id = run_ai_thread(
            validated_fields["thread_id"],
            validated_fields["assistant_id"],
            new_messages,
            validated_fields["ghl_contact_id"]
        )

        # Handle different response types
        if run_status == "completed":
            ai_content = process_message_response(
                validated_fields["thread_id"],
                run_id,
                validated_fields["ghl_contact_id"]
            )
            if not ai_content:
                return jsonify({"error": "No AI messages found"}), 404
            res_obj.add_message(ai_content)

        elif run_status == "requires_action":
            generated_function = process_function_response(
                validated_fields["thread_id"],
                run_id,
                run_response,
                validated_fields["ghl_contact_id"]
            )
            res_obj.add_action(generated_function["name"], generated_function["arguments"])

        else:
            # Handle other run statuses
            return jsonify({
                "stop": True,
                "technical_bug": run_status
            }), 200

        # Return the finalized response schema
        return jsonify(res_obj.get_response()), 200

    except Exception as e:
        # Capture and log the traceback
        tb_str = traceback.format_exc()
        log("error", "GENERAL -- Unhandled exception occurred with traceback",
            scope="General", error=str(e), traceback=tb_str)
        return jsonify({"error": str(e), "traceback": tb_str}), 500





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
