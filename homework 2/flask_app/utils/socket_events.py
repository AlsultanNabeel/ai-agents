"""
socket_events.py — handles real-time chat messages using WebSockets.

WEBSOCKETS vs. HTTP:
  When you visit /resume, your browser makes one HTTP request and gets one
  HTML response — then the connection closes. That's how most web pages work.

  WebSockets are different: the connection stays open, like a phone call.
  Both sides (browser and server) can send messages at any time without
  making a new request. This is why the chat feels instant.

HOW EVENTS WORK:
  Instead of URL routes, WebSockets use named events:
    - Browser emits 'send_message'  →  server handles it here
    - Server emits 'receive_message' →  browser displays the reply

  The @socketio.on(...) decorator works just like @app.route(...) in Flask,
  but for WebSocket events instead of HTTP requests.
"""

import secrets
import json
from threading import Lock

from flask_socketio import emit
from flask import current_app, request
from flask_app import socketio
from flask_app.utils.llm import (
    handle_ai_chat_request,
    apply_approved_write,
    create_request_trace
)
from flask_app.utils.database import (
    create_approval_grant,
    build_deletion_fingerprint
)
# Pending write proposals, isolated by Socket.IO connection ID.
pending_actions = {}
pending_actions_lock = Lock()


def log_request_trace(trace):
    """Print one structured request trace without sensitive credentials."""
    print(
        "[REQUEST TRACE] "
        + json.dumps(trace, ensure_ascii=False)
    )

@socketio.on('send_message')
def handle_message(data):
    """Handle chat messages and pending write approvals."""

    if not isinstance(data, dict):
        return

    user_message = data.get('message', '')

    if not isinstance(user_message, str):
        return

    user_message = user_message.strip()

    if not user_message:
        return

    db = current_app.db
    sid = request.sid
    normalized_message = user_message.casefold()

    trace = create_request_trace(user_message)

    # Check whether this connection has a pending proposal.
    with pending_actions_lock:
        pending = pending_actions.get(sid)

    if pending:
        if normalized_message in {"yes", "y"}:
            trace["route"] = "Approval"
            trace["route_reason"] = "User submitted approval for a pending proposal."
            trace["approval_state"] = "approved"
            trace["outcome"] = "approval_submitted"
            log_request_trace(trace)

            handle_approve_write({"token": pending["token"]})
            return

        if normalized_message in {"no", "n"}:
            trace["route"] = "Approval"
            trace["route_reason"] = "User rejected a pending proposal."
            trace["approval_state"] = "cancelled"
            trace["outcome"] = "cancelled"
            log_request_trace(trace)

            handle_reject_write({"token": pending["token"]})
            return

        ambiguous_replies = {
            "maybe", "hmm", "not sure", "i'm not sure",
            "im not sure", "perhaps", "uncertain"
        }

        if normalized_message in ambiguous_replies:
            trace["route"] = "Approval"
            trace["route_reason"] = "User did not provide a clear approval or rejection."
            trace["approval_state"] = "waiting"
            trace["outcome"] = "awaiting_clear_confirmation"
            log_request_trace(trace)

            emit(
                "receive_message",
                {
                    "response": "Please reply with 'yes' to approve or 'no' to cancel. No changes have been made."
                },
                to=sid
            )
            return

    # A different request invalidates the older proposal.
    with pending_actions_lock:
        invalidated = pending_actions.pop(sid, None)

    if invalidated:
        old_trace = invalidated.get("trace")

        if old_trace is not None:
            old_trace["approval_state"] = "cancelled"
            old_trace["outcome"] = "invalidated_by_new_request"
            log_request_trace(old_trace)

    try:
        ai_response = handle_ai_chat_request(
            db,
            role="Orchestrator",
            message=user_message,
            trace=trace
        )

        if (
            isinstance(ai_response, dict)
            and ai_response.get("status") == "pending_approval"
            and isinstance(
                ai_response.get("action", ai_response.get("proposal")),
                dict
            )
        ):
            action = ai_response.get(
                "action",
                ai_response.get("proposal")
            )

            token = secrets.token_urlsafe(32)

            with pending_actions_lock:
                pending_actions[sid] = {
                    "token": token,
                    "action": action,
                    "trace": trace
                }

            trace["approval_state"] = "waiting"
            trace["outcome"] = "awaiting_approval"
            log_request_trace(trace)

            emit(
                "write_approval_required",
                {
                    "token": token,
                    "proposal": action
                },
                to=sid
            )
            return

    except Exception as error:
        print(f"LLM error: {error}")
        trace["outcome"] = "error"
        ai_response = "Sorry, something went wrong answering that."

    if trace["outcome"] == "in_progress":
        trace["outcome"] = "completed"

    log_request_trace(trace)

    emit("receive_message", {"response": ai_response}, to=sid)

def build_resume_system_prompt(db):
    """
    Build the system prompt that gives the AI context about the resume.

    We pull the resume text directly from the database so the AI always
    has accurate, up-to-date information — no HTML scraping needed.

    Args:
        db: The database instance (set by create_app).

    Returns:
        str: A system prompt containing the AI's instructions + resume data.

    # QUESTION: What would you change in the instructions below to make
    #           the AI respond differently? Try changing the tone or focus.
    # QUESTION: What other information could you add to help the AI give
    #           better answers? (hobbies? goals? target job?)
    """
    resume_text = db.getResumeText()

    return f"""You are a helpful AI assistant reviewing a resume.
You have been given the resume content below. Use it to answer questions
accurately and helpfully. If asked something not covered in the resume,
say so honestly rather than guessing.
Keep answers concise. You may use light markdown (bold, bullet lists) but
avoid large tables.

RESUME CONTENT:
{resume_text}
"""

@socketio.on("approve_write")
def handle_approve_write(data):
    """Approve and execute a pending database change."""

    if not isinstance(data, dict):
        return

    token = data.get("token")

    if not isinstance(token, str):
        return

    sid = request.sid

    with pending_actions_lock:
        pending = pending_actions.get(sid)

        if not pending or not secrets.compare_digest(
            token, pending["token"]
        ):
            return

        trace = pending.get("trace")
        pending_actions.pop(sid, None)

    action = None

    try:
        action = pending["action"]
        approval_grant = None

        if action.get("operation") in {
            "delete_skill",
            "delete_all_skills"
        }:
            fingerprint = build_deletion_fingerprint(
                action["operation"],
                action["values"]["skill_ids"]
            )
            approval_grant = create_approval_grant(fingerprint)

        result = apply_approved_write(
            current_app.db,
            action,
            approval_grant=approval_grant
        )

        if trace is not None:
            trace["approval_state"] = "approved"

            operation = action.get("operation")
            if operation and operation not in trace["operations"]:
                trace["operations"].append(operation)

            trace["outcome"] = (
                "completed" if result.get("status") == "success" else "failed"
            )
            log_request_trace(trace)

        emit(
            "receive_message",
            {"response": result["message"]},
            to=sid
        )

    except Exception as error:
        print(f"Approved write failed: {error}")

        if trace is not None:
            trace["approval_state"] = "approved"

            if isinstance(action, dict):
                operation = action.get("operation")
                if operation and operation not in trace["operations"]:
                    trace["operations"].append(operation)

            trace["outcome"] = "failed"
            log_request_trace(trace)

        emit(
            "receive_message",
            {"response": "The approved change could not be completed."},
            to=sid
        )

@socketio.on("reject_write")
def handle_reject_write(data):
    """Reject a pending database change without modifying the database."""

    if not isinstance(data, dict):
        return

    token = data.get("token")

    if not isinstance(token, str):
        return

    sid = request.sid

    with pending_actions_lock:
        pending = pending_actions.get(sid)

        if not pending or not secrets.compare_digest(
            token, pending["token"]
        ):
            return

        trace = pending.get("trace")
        pending_actions.pop(sid, None)

    if trace is not None:
        trace["approval_state"] = "cancelled"
        trace["outcome"] = "cancelled"
        log_request_trace(trace)

    emit(
        "receive_message",
        {"response": "Proposed change rejected. No database changes were made."},
        to=sid
    )

@socketio.on("disconnect")
def handle_disconnect():
    """Clear pending approvals when a client disconnects."""

    with pending_actions_lock:
        pending_actions.pop(request.sid, None)
