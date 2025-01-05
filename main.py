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
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from asyncio import Queue
from typing import Dict

# Modify these constants at the top of the file after imports
MAX_CONCURRENT_REQUESTS = 6  # Increased from 3, leaving room for system processes
THREAD_POOL_SIZE = 8  # Match vCPU count
QUEUE_WORKERS = 4  # Number of workers processing queued requests

app = Flask(__name__)
app.thread_pool = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

# Request queue and processing settings
REQUEST_QUEUE: Dict[str, Queue] = {}  # Dictionary of queues per contact
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

async def get_or_create_queue(contact_id: str) -> Queue:
    """
    Get or create an unlimited queue for a specific contact
    """
    if contact_id not in REQUEST_QUEUE:
        REQUEST_QUEUE[contact_id] = Queue()  # Remove maxsize for unlimited queue
    return REQUEST_QUEUE[contact_id]

async def parallel_executor(func, *args, **kwargs):
    """
    Execute CPU-bound tasks in the thread pool
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(app.thread_pool, partial(func, *args, **kwargs))

async def process_queued_request(contact_id: str, request_data: dict):
    """
    Process a single request from the queue with optimized resource usage
    """
    async with processing_semaphore:
        queue = await get_or_create_queue(contact_id)
        
        try:
            res_obj = GHLResponseObject()
            
            # Validate request data using parallel executor
            validated_fields = await parallel_executor(
                validate_request_data, 
                request_data
            )
            if not validated_fields:
                return {"error": "Invalid request data"}, 400

            # Extract conversation ID
            ghl_convo_id = validated_fields["ghl_convo_id"]
            if validated_fields.get("add_convo_id_action"):
                res_obj.add_action("add_convo_id", {"ghl_convo_id": ghl_convo_id})

            # Process messages in parallel
            new_messages = await parallel_executor(
                retrieve_and_compile_messages,
                ghl_convo_id,
                validated_fields["ghl_recent_message"],
                validated_fields["ghl_contact_id"]
            )
            if not new_messages:
                return {"error": "No messages added"}, 400

            # Run AI processing in parallel
            run_response, run_status, run_id = await parallel_executor(
                run_ai_thread,
                validated_fields["thread_id"],
                validated_fields["assistant_id"],
                new_messages,
                validated_fields["ghl_contact_id"]
            )

            # Handle response types
            if run_status == "completed":
                ai_content = await parallel_executor(
                    process_message_response,
                    validated_fields["thread_id"],
                    run_id,
                    validated_fields["ghl_contact_id"]
                )
                if not ai_content:
                    return {"error": "No AI messages found"}, 404
                res_obj.add_message(ai_content)

            elif run_status == "requires_action":
                generated_function = await parallel_executor(
                    process_function_response,
                    validated_fields["thread_id"],
                    run_id,
                    run_response,
                    validated_fields["ghl_contact_id"]
                )
                res_obj.add_action(generated_function)

            else:
                log("error", f"AI Run Failed -- {validated_fields['ghl_contact_id']}", 
                    scope="AI Run", run_status=run_status, run_id=run_id, 
                    thread_id=validated_fields['thread_id'])
                return {"error": f"Run {run_status}"}, 400

            return res_obj.get_response(), 200
            
        except Exception as e:
            tb_str = traceback.format_exc()
            log("error", "QUEUE -- Request processing failed",
                scope="Queue", error=str(e), traceback=tb_str,
                contact_id=contact_id)
            return {"error": str(e), "traceback": tb_str}, 500
        finally:
            # Remove completed request from queue
            await queue.get()
            queue.task_done()

# Main conversation endpoint that handles AI assistant interactions
@app.route('/moveConvoForward', methods=['POST'])
async def move_convo_forward():
    """
    Asynchronous endpoint with request queueing for handling conversation flow.
    All requests are accepted and processed in order per contact.
    """
    try:
        request_data = request.json
        
        # Basic validation for contact ID
        if not request_data.get("ghl_contact_id"):
            return jsonify({"error": "Missing contact ID"}), 400
            
        contact_id = request_data["ghl_contact_id"]
        
        # Get or create queue for this contact
        queue = await get_or_create_queue(contact_id)
        
        # Add request to queue
        await queue.put(request_data)
        log("info", f"Request queued for contact {contact_id}", 
            queue_size=queue.qsize())
        
        # Process the request
        response, status_code = await process_queued_request(contact_id, request_data)
        return jsonify(response), status_code

    except Exception as e:
        tb_str = traceback.format_exc()
        log("error", "GENERAL -- Unhandled exception in queue processing",
            scope="General", error=str(e), traceback=tb_str)
        return jsonify({"error": str(e), "traceback": tb_str}), 500


# Test endpoint for API response format verification
@app.route('/testEndpoint', methods=['POST'])
def possibleFormat():
    """
    Test endpoint that demonstrates the expected response format
    """
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

@app.teardown_appcontext
def cleanup(error):
    """
    Clean up resources when the application shuts down
    """
    if hasattr(app, 'thread_pool'):
        app.thread_pool.shutdown(wait=True)

# Application entry point
if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
