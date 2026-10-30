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
from flask_app.utils.llm import (
    send_message,
    coordinator_agent,
    database_read_expert,
    database_write_expert
)
from flask import current_app
from flask import request

pending_skills = {}





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
    print("DEBUG: Received message:", user_message, flush=True)

    if not user_message:
        return

    # Build the system prompt that tells the AI about the student's resume.
    # This is what makes it a "resume reviewer" rather than a generic chatbot.
    system_prompt = build_resume_system_prompt(current_app.db)

    # Send the message to OpenRouter and get the AI's reply.
    # If anything goes wrong (bad key, no internet, API error), we catch the
    # exception and emit a helpful error message instead of hanging silently.
    try:
        ai_response = "Sorry, I couldn't process your request."
        message_lower = user_message.lower().strip()

        print("DEBUG: Pending skills:", pending_skills, "Current SID:", request.sid, flush=True)

        if request.sid in pending_skills and (
            message_lower.startswith("yes") or message_lower == "confirm"
         ):
             skill_name, skill_level, experience_name = pending_skills[request.sid]
             experience_id = current_app.db.getExperienceId(experience_name)

             if experience_id is None:
                ai_response = f"Experience '{experience_name}' was not found."
             else:
                print("Database Write Expert Python code:")
                print(
                    f"current_app.db.addSkill({skill_name!r}, "
                    f"{int(skill_level)}, {experience_id!r})",
                    flush=True
                )
                
                current_app.db.addSkill(
                    skill_name, int(skill_level), experience_id
                )
                ai_response = f"Successfully saved '{skill_name}' with level {skill_level}!"

             pending_skills.pop(request.sid, None)
             emit("receive_message", {"response": ai_response})
             return
    
        print("DEBUG: Starting coordinator agent", flush=True)
        decision = coordinator_agent(current_app.db, user_message)
        print("DEBUG: Coordinator decision =", repr(decision), flush=True)

        if decision == "READ":
            result = database_read_expert(current_app.db, user_message)
            ai_response = send_message(
               f"Answer this question using the database result: {result}\nQuestion: {user_message}",
               system_prompt
            )
       
        elif decision == "WRITE":
            skill_name, skill_level, experience_name = database_write_expert(
                 current_app.db, user_message
            )
            pending_skills[request.sid] = (skill_name, skill_level, experience_name)

            ai_response = (
                f"I understood that you want to add '{skill_name}' "
                f"with level {skill_level} "
                f"to '{experience_name}'. "
                "Please confirm before I save it."
            )
        elif decision == "BOTH":
             print("DEBUG: Orchestrator selected BOTH", flush=True)
             print(
                "Orchestrator Plan:\n"
                "1. Call Database Read Expert to check whether the skill exists.\n"
                "2. If the skill does not exist, call Database Write Expert to add it.\n"
                "3. Return the result to the user.",
                flush=True
            )

             # Step 1: Extract the requested skill details
             print("Orchestrator: Extracting requested skill details", flush=True)
             skill_name, skill_level, experience_name = database_write_expert( 
                current_app.db, user_message
             )

           # Step 2: Check whether this skill already exists
             print("Orchestrator: Calling Database Read Expert", flush=True)

             read_result = database_read_expert(
             current_app.db,
            f"Does the skill '{skill_name}' exist in the experience '{experience_name}'?"
             )

             print("Database Read Expert result:", read_result, flush=True)
             existing_skills = current_app.db.query(
                    """
                     SELECT s.skill_id
                     FROM skills s
                     JOIN experiences e ON s.experience_id = e.experience_id
                     WHERE LOWER(s.name) = LOWER(?)
                      AND LOWER(e.name) = LOWER(?)
                     """,
                     (skill_name, experience_name)
             )
        
             skill_exists = len(existing_skills) > 0

             if skill_exists:
                 ai_response = f"'{skill_name}' already exists in '{experience_name}'."
             else:

                 # Step 4: Find the correct experience
                 experiences = current_app.db.query(
                    """
                    SELECT experience_id
                    FROM experiences
                    WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
                    """,
                    (experience_name,)
                 )

                 if not experiences:
                  ai_response = f"Experience '{experience_name}' was not found."

                 else:
                     #Step 5: Store the skill and wait for confirmation
                     pending_skills[request.sid] = (
                         skill_name,
                         skill_level,
                         experience_name
                         )
                     ai_response = (
                         f"'{skill_name}' was not found. "
                         f"Do you want to add it with level {skill_level} "
                         f"to '{experience_name}'? "
                         "Please confirm before I save it."
                     )
        else:
                     ai_response = "Sorry, I couldn't understand your request."
        
    except Exception as error:
        import traceback; traceback.print_exc()
        print(f"LLM error: {error}")
        
        ai_response = f"⚠️ Could not reach the AI: {error}"

    # Emit the reply back — the browser's socket.on('receive_message') picks this up
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
