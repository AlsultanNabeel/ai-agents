"""
llm.py — sends messages to an AI language model via the OpenRouter API.

This file is the bridge between your Flask app and an AI model (GPT-3.5).
When a student types a message in the chat, it travels here, gets sent to
OpenRouter, and the AI's reply comes back.

KEY CONCEPTS:
  - API (Application Programming Interface): a way for two programs to talk
    to each other over the internet. OpenRouter exposes an API we can call.
  - HTTP POST request: sending data to a server (like submitting a form).
    We POST the conversation to OpenRouter and it POSTs back the AI reply.
  - System prompt: instructions given to the AI before the conversation starts.
    Think of it as the AI's job description.
"""

from email.mime import message
from logging import config
import os
import requests
from jinja2 import Template
import re
import ast 
import json
# The URL we send our messages to.
# OpenRouter acts as a single gateway to many different AI models.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Which AI model to use. OpenRouter supports many models.
# Models with ':free' suffix are free to use — no API credits needed.
# See all available models at: https://openrouter.ai/models
# QUESTION: What would change if you switched to a different model?
#           Try 'google/gemma-2-9b-it:free' or 'mistralai/mistral-7b-instruct:free'.
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl:free"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
# One shared template for every expert's system prompt. Each expert just
# fills in different values for role/domain/instructions/context/examples.
#
# We use Jinja2 here (not manual string replacement) because it's already a
# Flask dependency — it's the exact same {{ }} / {% if %} syntax you've been
# reading in resume.html, just rendering a prompt string instead of a page.
MASTER_TEMPLATE = Template("""\
You are a {{ role }}, an expert in {{ domain }}.

{{ specific_instructions }}
{% if background_context %}
Context:
{{ background_context }}
{% endif %}
{% if few_shot_examples %}
Examples:
{{ few_shot_examples }}
{% endif %}
Request: {{ request }}
""", trim_blocks=True, lstrip_blocks=True)


def fill_template(role, domain, specific_instructions, request,
                   background_context="", few_shot_examples=""):
    """
    Render MASTER_TEMPLATE into one expert's full system prompt.

    background_context and few_shot_examples are optional: the {% if %}
    blocks above drop the whole section — header included — when the
    argument is empty, instead of leaving a dangling "Context:" with
    nothing underneath it.
    """
    return MASTER_TEMPLATE.render(
        role=role,
        domain=domain,
        specific_instructions=specific_instructions,
        background_context=background_context,
        few_shot_examples=few_shot_examples,
        request=request,
    ).strip()
def send_message(user_message, system_prompt="You are a helpful assistant."):
    """
    Send a message to the AI and return its response as a string.

    Args:
        user_message  (str): The message the user typed in the chat.
        system_prompt (str): Instructions that define how the AI should behave.
                             This is sent before the user message, every time.

    Returns:
        str: The AI's reply text, or an error message if something went wrong.

    HOW IT WORKS:
        We build a 'messages' list with two entries:
          1. system — gives the AI its instructions (the resume context)
          2. user   — the student's actual question
        We send this list to OpenRouter, which forwards it to the AI model
        and returns the generated reply.

    # NOTE: This function has no memory — each call starts fresh.
    #       Every message includes the full system prompt but no chat history.
    # QUESTION: How would you modify this to remember previous messages?
    #           Hint: you would need to store past messages and include them
    #           in the 'messages' list between the system and user entries.
    """
    api_key = os.getenv('OPENROUTER_API_KEY')

    # If the .env file is missing or the key was not filled in, tell the user
    # immediately rather than making a doomed API call that will just hang.
    if not api_key or api_key == 'paste-your-key-here':
        return "⚠️ No API key found. Add your OpenRouter key to the .env file and restart the app."

    # The Authorization header tells OpenRouter who we are.
    # "Bearer" is just a standard prefix for API key authentication.
    # NEVER hardcode the api_key here — always load it from the .env file.
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8080"   # identifies our app to OpenRouter
    }

    # The messages list defines the conversation context for the AI.
    # 'system' sets the AI's role and knowledge before it sees our question.
    # 'user' is the message the student actually typed.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message}
    ]

    # Send the HTTP POST request to OpenRouter.
    # timeout=30 means: give up if we don't hear back within 30 seconds.
    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json={"model": DEFAULT_MODEL, "messages": messages},
        timeout=30
    )

    result = response.json()
      # QUESTION: Print result here and see what OpenRouter actually sends back.
    # OpenRouter sometimes returns HTTP 200 but with an 'error' field instead
    # of 'choices' — this happens with a bad API key or an invalid request.
    # QUESTION: Print result here and see what OpenRouter actually sends back.
    if 'error' in result:
        error_message = result['error'].get('message', 'Unknown API error')
        return f"⚠️ OpenRouter error: {error_message}"

    if 'choices' not in result:
        return f"⚠️ Unexpected response from OpenRouter: {result}"

    return result['choices'][0]['message']['content']

def handle_ai_chat_request(db, role, message):
    """
    Route a chat message to the named expert. role=None keeps Homework 0's
    original single-prompt behavior as a fallback, so nothing about the
    basic chat flow breaks while you're building this out.
    """
    if role is None:
        return send_message(message)

    config = db.getLLMRoles()[role]
    background_context = config['background_context'] or ""
    if role == "Content Expert":
        # No page-scraping in this stack -- "current page content" is the
        # resume data itself, fetched fresh on every request.background_context += "\n" + db.getResumeText()
        background_context += "\n" + db.getResumeText()
    system_prompt = fill_template(
        role=config['role'],
        domain=config['domain'],
        specific_instructions=config['specific_instructions'],
        background_context=background_context,
        few_shot_examples=config['few_shot_examples'] or "",
        request=message,
    )

    if role == "Database Write Expert":
        system_prompt += """
Return ONLY valid JSON. No Python code or markdown.

For adding a skill, use:
{"operation": "add_skill", "name": "Python", "experience_id": 1, "skill_level": 3}

Use actual database values. Never invent missing values.
For deleting a skill, return ONLY:
{"operation": "delete_skill", "skill_id": 1}

Use the actual skill ID. Never invent IDs.
"""

    output = send_message(message, system_prompt).strip()
    print(f"[{role}] generated:\n{output}\n")

    if role == "Database Read Expert":
      return execute_read_query(db, output)
    if role == "Semantic Search Expert":
        results = db.semanticSearch(message)
        if not results:
         return "No relevant information found."
        return str(results)

    if role == "Database Write Expert":
        return execute_write_action(db, output)

    if role == "Orchestrator":
        return run_orchestrator_plan(db, message, output)

    return output


def run_orchestrator_plan(db, original_request, plan_text):
    """
    Parse the Orchestrator's plan (a Python list of call strings), run each
    expert call in order, then make one final call to turn the raw results
    into a single clean reply for the chat UI.
    """
    try:
        plan_text = plan_text.strip()  
        clean_plan = plan_text.strip()
        clean_plan = clean_plan.replace(chr(96) * 3 + 'python', '').replace(chr(96) * 3, '').strip()
        call_strings = ast.literal_eval(clean_plan)  # the Orchestrator's own list literal
        if isinstance(call_strings, str):
            call_strings = [call_strings]
    except Exception:
        print(f"Orchestrator returned an unparseable plan: {plan_text}")
        return "Sorry, I couldn't plan a response to that."

    results = []
    for call_string in call_strings:
        print(f"[Orchestrator] executing: {call_string}")
        match = re.search(r'role="([^"]*)",\s*message="([^"]*)"', call_string)
        if not match:
            print(f"Invalid orchestrator step: {call_string}")
            continue
        
        role, message = match.group(1), match.group(2)
        if role == "Semantic Search Expert":
            response = db.semanticSearch(message)
            if not response:
                response = "No relevant information found."
        else:
            response = handle_ai_chat_request(db, role, message)

        results.append((role, message, response))

    steps_summary = "\n".join(f"{r}: {resp}" for r, m, resp in results)
    synthesis_prompt = (
        f'The user asked: "{original_request}"\n\n'
        f"Here is what each expert found or did:\n{steps_summary}\n\n"
        "Write ONE short, clear reply. A Database Write Expert step's result "
        "is already the exact message to show the user (e.g. 'New Python "
        "added to the skills table.') -- if one is present, reuse it "
        "verbatim rather than rephrasing it. Otherwise, summarize the "
        "other results in plain language. Never mention SQL, Python, code, "
        "or these internal steps."
    )
    return send_message(original_request, synthesis_prompt)
def execute_read_query(db, sql):
    """
    Run the Database Read Expert's generated SQL. We refuse anything that
    isn't a SELECT -- this expert is read-only by design, so there's never
    a legitimate reason to run anything else, even if a user's message
    somehow tricks the model into generating something else.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Sorry, I couldn't safely answer that question."
    try:
        return str(db.query(sql))
    except Exception as error:
        print(f"Read Expert query failed: {error}")
        return "Sorry, that question couldn't be answered."
class ApprovalRequired(Exception):
    def __init__(self, action, description):
        super().__init__(description)
        self.action = action
        self.description = description

def execute_write_action(db, generated_code, approved=False):
    try:
        action = json.loads(generated_code)

        if not isinstance(action, dict):
            return "Invalid action."

        operation = action.get("operation")

        if operation == "add_skill":
            name = action.get("name")
            experience_id = action.get("experience_id")
            level = action.get("skill_level")

            if not isinstance(name, str) or not name.strip():
                return "Invalid skill name."

            if type(experience_id) is not int or experience_id <= 0:
                return "Invalid experience ID."

            if type(level) is not int or not 1 <= level <= 10:
                return "Invalid skill level."

            if not db.query(
                "SELECT experience_id FROM experiences WHERE experience_id = ?",
                (experience_id,)
            ):
                return "Experience not found."

            db.query(
                "INSERT INTO skills (experience_id, name, skill_level) VALUES (?, ?, ?)",
                (experience_id, name.strip(), level)
            )
            return "Skill added successfully."

        if operation == "delete_skill":
            skill_id = action.get("skill_id")

            if type(skill_id) is not int or skill_id <= 0:
                return "Invalid skill ID."

            rows = db.query(
                "SELECT skill_id, name FROM skills WHERE skill_id = ?",
                (skill_id,)
            )

            if not rows:
                return "Skill not found."

            name = rows[0]["name"]

            if not approved:
                raise ApprovalRequired(
                    {
                        "operation": "delete_skill",
                        "skill_id": skill_id,
                        "name": name
                    },
                    f"Delete skill '{name}' (ID {skill_id})?"
                )

            if action.get("name") != name:
                return "Skill changed. Deletion cancelled."

            db.query(
                "DELETE FROM skills WHERE skill_id = ?",
                (skill_id,)
            )
            return "Skill deleted successfully."

        return "Operation not supported."

    except ApprovalRequired:
        raise

    except (ValueError, TypeError, KeyError):
        return "Invalid action."

    except Exception as error:
        print(f"Write failed: {error}")
        return "Operation was unsuccessful."
     
def get_embedding(text):
    model = os.getenv("EMBEDDING_MODEL")
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not model or not api_key:
        raise ValueError("Missing embedding configuration")

    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "input": text
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()
    embedding = data["data"][0]["embedding"]

    if not embedding or not any(
        value != 0 for value in embedding
    ):
        raise ValueError("Invalid embedding")

    return embedding