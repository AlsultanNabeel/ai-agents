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

from flask_socketio import emit
from flask_app import socketio
from flask_app.utils.llm import handle_ai_chat_request
from flask import current_app

# This is set by create_app() in __init__.py so this file can use the database.


@socketio.on('send_message')
def handle_message(data):
    """
    Called automatically when the browser emits a 'send_message' event.

    Args:
        data (dict): Contains 'message' — the text the student typed.

    Flow:
        1. Extract the user's message from the event data
        2. Build a system prompt from the student's resume (from the database)
        3. Send both to the AI via llm.py
        4. Emit the AI's reply back to the browser as 'receive_message'

    # NOTE: 'emit' sends a named event back to the browser.
    #       The browser is listening for 'receive_message' — see resume.html.
    # QUESTION: Right now, every connected user receives every message.
    #           How would you send a reply only to the user who asked?
    #           Hint: look up 'rooms' in the Flask-SocketIO documentation.
    """
    user_message = data.get('message', '').strip()
    db = current_app.db
    if not user_message:
        return
    try:
        ai_response = handle_ai_chat_request(db, role="Orchestrator", message=user_message)
    except Exception as error:
        print(f"LLM error: {error}")
        ai_response = "Sorry, something went wrong answering that."
    emit('receive_message', {'response': ai_response})



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
