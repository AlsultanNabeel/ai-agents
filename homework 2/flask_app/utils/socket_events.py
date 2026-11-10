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
import re 
from flask_socketio import emit
from flask_app import socketio
from flask_app.utils.llm import handle_ai_chat_request
from flask import current_app

YES = re.compile(r"^\s*(yes|y)\s*[.!]?\s*$", re.I)
NO = re.compile(r"^\s*(no|n|cancel)\s*[.!]?\s*$", re.I)

@socketio.on('send_message')
def handle_message(data):
    user_message = data.get('message', '').strip()
    if not user_message:
        return

    db = current_app.db

    # A deletion is waiting: this message is the user's answer to it.
    if db.pending:
        if YES.match(user_message):
            emit('receive_message', {'response': db.confirmDelete()})
            return
        if YES.match(user_message):
            message = db.confirmDelete()
            db.syncEmbeddings()                       # remove the deleted skills' embeddings
            emit('receive_message', {'response': message})
            return
        db.cancelDelete()   # anything else ("maybe", a new question): cancel it, then
                            # treat the message as a normal new request below

    try:
        ai_response = handle_ai_chat_request(db, role="Orchestrator", message=user_message)
    except Exception as error:
        print(f"LLM error: {error}")
        ai_response = "Sorry, something went wrong answering that."
    db.syncEmbeddings()                               # embed anything the chat just added       
    emit('receive_message', {'response': ai_response})
