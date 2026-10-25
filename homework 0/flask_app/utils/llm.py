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

# The URL we send our messages to.
# OpenRouter acts as a single gateway to many different AI models.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Which AI model to use. OpenRouter supports many models.
# Models with ':free' suffix are free to use — no API credits needed.
# See all available models at: https://openrouter.ai/models
# QUESTION: What would change if you switched to a different model?
#           Try 'google/gemma-2-9b-it:free' or 'mistralai/mistral-7b-instruct:free'.
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning: free"


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
        print("OpenRouter error details:", result)
        error_message = result['error'].get('message', 'Unknown API error')
        return f"⚠️ OpenRouter error: {error_message}"

    if 'choices' not in result:
        return f"⚠️ Unexpected response from OpenRouter: {result}"

    return result['choices'][0]['message']['content']
