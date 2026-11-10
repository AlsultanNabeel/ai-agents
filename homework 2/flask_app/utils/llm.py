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

import os
import requests
import re
import json
from flask_app.utils import embeddings

# The URL we send our messages to.
# OpenRouter acts as a single gateway to many different AI models.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Which AI model to use. OpenRouter supports many models.
# Models with ':free' suffix are free to use — no API credits needed.
# See all available models at: https://openrouter.ai/models
# QUESTION: What would change if you switched to a different model?
#           Try 'google/gemma-2-9b-it:free' or 'mistralai/mistral-7b-instruct:free'.

from jinja2 import Template

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


DEFAULT_MODEL = "openai/gpt-4o-mini"


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

    if role in SEARCH_ROLES:        # search experts don't call the language model
        print(f"[{role}] searching for: {message}")
        return semantic_search(db, message, SEARCH_ROLES[role])[0]

    config = db.getLLMRoles()[role]
    background_context = config['background_context'] or ""
    if role == "Content Expert":
        # No page-scraping in this stack -- "current page content" is the
        # resume data itself, fetched fresh on every request.
        background_context += "\n" + db.getResumeText()

    system_prompt = fill_template(
        role=config['role'],
        domain=config['domain'],
        specific_instructions=config['specific_instructions'],
        background_context=background_context,
        few_shot_examples=config['few_shot_examples'] or "",
        request=message,
    )
    output = send_message(message, system_prompt).strip()
    print(f"[{role}] generated:\n{output}\n")   # the rubric checks this output

    if role == "Database Read Expert":
        return execute_read_query(db, output)
    if role == "Database Write Expert":
        return execute_write_action(db, output)
    if role == "Orchestrator":
        return run_orchestrator_plan(db, message, output)
    return output   # Content Expert -- output is already the final answer

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

def execute_write_action(db, raw_output):
    """
    The Write Expert answers with ONE JSON operation, e.g. {"op": "delete_skill", "name": "Python"}.
    We check the operation and every value, then call a fixed database method.
    Nothing the model writes is ever executed as code. Deletions only PREVIEW here;
    the real delete happens in db.confirmDelete(), after the user says yes.
    """
    text = re.sub(r"^```\w*\s*|\s*```$", "", raw_output.strip()).strip()
    try:
        action = json.loads(text)
    except ValueError:
        print(f"Write Expert did not return valid JSON: {raw_output}")
        return "Operation was unsuccessful."

    op = action.get("op") if isinstance(action, dict) else None
    name = action.get("name") if isinstance(action, dict) else None
    experience = action.get("experience_name") if isinstance(action, dict) else None
    experience = experience.strip() if isinstance(experience, str) and experience.strip() else None

    if op == "add_skill":
        level = action.get("skill_level")
        if (isinstance(name, str) and name.strip() and experience
                and isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 10):
            return db.addSkill(experience, name.strip(), level)
        return "I can't do that: the skill details are incomplete."

    if op == "delete_skill":
        if isinstance(name, str) and name.strip():
            return db.deleteSkill(name.strip(), experience)
        return "I can't do that: which skill should be deleted?"

    if op == "delete_all_skills":
        return db.deleteAllSkills()

    print(f"Write Expert asked for an operation that is not allowed: {raw_output}")
    return "I can't do that."

# Search experts: role name -> tables to compare against (None = every table)
SEARCH_ROLES = {"Semantic Search Expert": None, "Skill Search Expert": ["skills"]}

ALLOWED_ROLES = {"Database Read Expert", "Database Write Expert", "Content Expert"} | set(SEARCH_ROLES)
MAX_STEPS = 4


def semantic_search(db, query, tables=None):
    """
    Search by meaning. Returns (text_for_the_user, value_for_a_later_step).
    The value is None when nothing relevant was found or the search is unavailable.
    """
    try:
        hits = embeddings.search(db, query, tables=tables)
    except embeddings.EmbeddingError as error:
        print(f"Search failed: {error}")
        return "Search by meaning is unavailable right now.", None
    if not hits:
        return "No relevant records found.", None
    lines = [f"{h['table']} id {h['id']} (similarity {h['score']}): {h['text']}" for h in hits]
    top = hits[0]
    return "\n".join(lines), f"{top['table']} id {top['id']} ({top['text'][:100]})"


def run_orchestrator_plan(db, original_request, plan_text):
    """
    Read the Orchestrator's plan, run each expert call in order, then make one final
    call that turns the results into a single reply. A later step can use an earlier
    step's result by writing {{step1}} (or {{step2}}...) in its message.
    """
    db.pending = None   # a new request cancels any older pending deletion

    # Read the plan as DATA (a regex finds each role/message pair); nothing is executed.
    calls = re.findall(r'role="([^"]*)",\s*message="([^"]*)"', plan_text)
    if not calls or len(calls) > MAX_STEPS or any(role not in ALLOWED_ROLES for role, _ in calls):
        print(f"Orchestrator returned an unusable plan: {plan_text}")
        return "Sorry, I couldn't plan a response to that."

    results, values = [], []
    for number, (role, message) in enumerate(calls, start=1):
        for earlier, value in enumerate(values, start=1):
            message = message.replace("{{step%d}}" % earlier, str(value))
        if re.search(r"\{\{step\d+\}\}", message):      # refers to a step that has not run
            print(f"Orchestrator plan refers to a later step: {plan_text}")
            return "Sorry, I couldn't plan a response to that."
        print(f"[Orchestrator] step {number}: {role}: {message}")

        if role in SEARCH_ROLES:
            response, value = semantic_search(db, message, SEARCH_ROLES[role])
            needed_later = any("{{step%d}}" % number in later for _, later in calls[number:])
            if value is None and needed_later:
                return f"I couldn't find anything relevant to '{message}', so I stopped there."
            if value is None:
                value = response
        else:
            response = handle_ai_chat_request(db, role, message)
            value = response

        results.append((role, message, response))
        values.append(value)
        if db.pending:      # a deletion is waiting for the user's answer: stop here
            break

    # If a deletion is waiting for the user's answer, show its exact preview (never reword it).
    if db.pending:
        return db.pending["message"]

    steps_summary = "\n".join(f"{r}: {resp}" for r, m, resp in results)
    synthesis_prompt = (
        f'The user asked: "{original_request}"\n\n'
        f"Here is what each expert found or did:\n{steps_summary}\n\n"
        "Write ONE short, clear reply using ONLY the information above. "
        "If a step reports that nothing relevant was found, or that something is unavailable, "
        "say so plainly - never invent records, names or numbers. A Database Write Expert step's "
        "result is already the exact message to show the user (e.g. 'New Python added to the "
        "skills table.') -- if one is present, reuse it verbatim rather than rephrasing it. "
        "Otherwise, summarize the other results in plain language. Never mention SQL, Python, "
        "code, similarity scores or these internal steps."
    )
    return send_message(original_request, synthesis_prompt)