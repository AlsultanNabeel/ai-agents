"""
app.py — the entry point for the application.

Run this file to start the web server:
    python app.py

Then open your browser to: http://localhost:8080

HOW THIS WORKS:
  1. create_app() (in flask_app/__init__.py) sets up the Flask app:
       - loads your .env file (API key, etc.)
       - creates the SQLite database and loads CSV data
       - registers routes and WebSocket event handlers
  2. socketio.run() starts the web server with WebSocket support.
     We use socketio.run() instead of app.run() because regular Flask
     doesn't support WebSockets — flask-socketio adds that capability.

WHY debug=True?
  In debug mode, Flask automatically restarts when you save a Python file.
  This means you don't have to stop and restart the server manually.
  Note: CSV changes still require a restart because the database is loaded
  once at startup.
"""

from flask_app import create_app

# Build the app and get the socketio instance back
app, socketio = create_app()

if __name__ == "__main__":
    print("Starting AI Resume Agent...")
    print("Open your browser to: http://localhost:8080")
    # NOTE: use_reloader=False is required with eventlet.
    # Werkzeug's reloader starts the app twice, and the second process
    # tries to bind the same port while the first is already using it.
    # To see Python changes, stop the server (Ctrl+C) and restart it.
    # HTML/CSS/JS changes are visible on browser refresh with no restart needed.
    socketio.run(app, host='0.0.0.0', port=8080, debug=True, use_reloader=False)
