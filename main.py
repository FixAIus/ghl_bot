import os
from flask import Flask, jsonify, request
from functions import (
    log,
    extract_fields,
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
        # Validate request data
        validated_fields = validate_request_data(request.json)
        if not validated_fields:
            return jsonify({"error": "Missing required fields"}), 400

        # Process conversation ID
        ghl_convo_id = validated_fields["ghl_convo_id"]
        if not ghl_convo_id or ghl_convo_id in ["", "null"]:
            ghl_convo_id = get_conversation_id(validated_fields["ghl_contact_id"])
            if not ghl_convo_id:
                return jsonify({"error": "Failed to retrieve conversation ID"}), 500

        # Retrieve and process messages
        new_messages = retrieve_and_compile_messages(
            ghl_convo_id,
            validated_fields["ghl_recent_message"],
            validated_fields["ghl_contact_id"]
        )
        if not new_messages:
            return jsonify({"error": "No new messages to process"}), 200

        # Run AI thread and get response
        run_response, run_status, run_id = run_ai_thread(
            validated_fields["thread_id"],
            validated_fields["assistant_id"],
            new_messages[::-1],
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
            return jsonify({
                "ai_response": ai_content,
                "ghl_convo_id": ghl_convo_id
            }), 200

        elif run_status == "requires_action":
            stop_reason = process_function_response(
                validated_fields["thread_id"],
                run_id,
                run_response,
                validated_fields["ghl_contact_id"]
            )
            return jsonify({
                "ghl_convo_id": ghl_convo_id,
                "stop": stop_reason
            }), 200

        # Handle other run statuses
        return jsonify({
            "stop": True,
            "technical_bug": run_status
        }), 200

    except Exception as e:
        log("error", "GENERAL -- Unhandled exception occurred", 
            scope="General", error=str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
