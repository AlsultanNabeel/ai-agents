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
import json
from flask_app.utils.embeddings import search, EmbeddingError
from flask_app.utils.operations import parse_operation, perform_operation, OperationError


# The URL we send our messages to.
# OpenRouter acts as a single gateway to many different AI models.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Which AI model to use. OpenRouter supports many models.
# Models with ':free' suffix are free to use — no API credits needed.
# See all available models at: https://openrouter.ai/models
# QUESTION: What would change if you switched to a different model?
#           Try 'google/gemma-2-9b-it:free' or 'mistralai/mistral-7b-instruct:free'.
DEFAULT_MODEL = "openai/gpt-4o-mini"

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

    if role == "Semantic Search Expert":
        return run_semantic_search(db, message)

    config = db.getLLMRoles()[role]
    background_context = config['background_context'] or ""
    if role in ("Content Expert", "Database Write Expert"):
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

def run_semantic_search(db, query):
    # Skill questions only search the skills table (see the S2 measurements)
    tables = ['skills'] if 'skill' in query.lower() else None
    try:
        results = search(db, query, tables=tables)
    except EmbeddingError as error:
        print(f"[Semantic Search Expert] embedding failed: {error}")
        return "Search failed: the embedding service is unavailable, so nothing could be looked up."

    print(f"[Semantic Search Expert] query={query!r} tables={tables or 'all'}")
    for result in results:
        print(f"    {result['score']:.3f}  {result['table']} #{result['id']}  {result['text']}")
    if not results:
        return "No matching records found."
    return "\n".join(
        f"{result['table']} #{result['id']}: {result['text']} (score {result['score']})"
        for result in results
    )



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


def execute_write_action(db, output):
    """
    The Write Expert no longer writes code. It picks one allowed operation and
    fills in its values as JSON; we check all of it before anything runs.
    A destructive operation raises ApprovalRequired instead of running.
    """
    try:
        operation = parse_operation(db, output)
    except OperationError as error:
        print(f"[Database Write Expert] rejected: {error}")
        return f"Operation was unsuccessful: {error}."
    print(f"[Database Write Expert] operation: {operation}")
    return perform_operation(db, operation)


ALLOWED_EXPERTS = {"Database Read Expert", "Database Write Expert", "Content Expert", "Semantic Search Expert"}


def parse_plan(plan_text):
    plan = json.loads(plan_text)
    if not isinstance(plan, list):
        raise ValueError("the plan must be a JSON list")
    for step in plan:
        if not isinstance(step, dict) or step.get('role') not in ALLOWED_EXPERTS \
                or not isinstance(step.get('message'), str):
            raise ValueError(f"invalid step: {step!r}")
    return plan


def run_orchestrator_plan(db, original_request, plan_text):
    """
    Read the Orchestrator's plan as JSON data, run each step in order, then
    make one final call to turn the raw results into one clean reply.
    """
    try:
        plan = parse_plan(plan_text)
    except ValueError as error:
        print(f"Orchestrator returned an invalid plan ({error}): {plan_text}")
        return "Sorry, I couldn't plan a response to that."
    if not plan:
        return "I'm not sure what you'd like me to do. Could you say it as a full request?"

    results = []

    for number, step in enumerate(plan, start=1):
        role, message = step['role'], step['message']
        print(f"[Orchestrator] step {number}: {role} <- {message!r} | reason: {step.get('reason', 'none given')}")

        # Later steps get what earlier steps found, so they can use it
        if results:
            earlier = "\n".join(f"{r}: {resp}" for r, m, resp in results)
            message += f"\n\nResults from earlier steps:\n{earlier}"
        if role == "Semantic Search Expert":
            # Search with the user's own words: the cut-off was measured on full questions,
            # and the Orchestrator's shortened text ("Harvard experience") scored noise higher
            response = run_semantic_search(db, original_request)
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
        "or these internal steps. If the results say nothing was found, say so "
        "plainly and never invent a record."
    )
    return send_message(original_request, synthesis_prompt)
