# AI Resume Agent — Homework 2

## Overview

This project extends the AI Resume Agent with semantic search, persistent embeddings, expert-based request routing, and an approval workflow for database modifications.

## Requirements

- Python 3.10 or later
- An OpenRouter API key
- Internet connection for API requests

## Setup

Run these commands from the `homework 2` directory:

```bash
# Create and activate a virtual environment (if needed)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your local environment file
cp .env.example .env
```

Open `.env` and configure the following variables:

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `EMBEDDING_MODEL` | Embedding model identifier |
| `RESUME_DB_PATH` | Optional SQLite database path |

Do not commit `.env` or share your API key.

## Run the application

From the `homework 2` directory:

```bash
python app.py
```

Open the application at:

http://localhost:8080

To stop the server, press `Ctrl+C` in the terminal.

## Run the tests

Run the scenario test suite:

```bash
python tests/run_scenarios.py
```

The test runner uses an isolated temporary SQLite database so that tests do not modify the application's persistent resume database.

Some scenarios require API access. Check the test output to distinguish locally executed tests from scenarios requiring API configuration.

## Reset test data

The scenario test runner creates its own temporary database and removes it when the process exits. No manual reset is required between test runs.

To reset the application's local database instead:

1. Stop the application.
2. Back up any data you want to keep.
3. Remove the application's SQLite database file:

```bash
rm -f flask_app/database/resume.db
```

4. Restart the application:

```bash
python app.py
```

The application will recreate the database and initialize its CSV-backed data.

**Warning:** Resetting the application database deletes locally stored changes. Do not run this command if you need to preserve them.

## Project structure

```text
homework 2/
├── app.py
├── flask_app/
│   ├── database/
│   ├── routes/
│   └── utils/
├── instance/
├── tests/
│   └── run_scenarios.py
├── .env.example
├── README.md
├── DESIGN_AND_TESTING.md
└── requirements.txt
```

## Documentation

See [DESIGN_AND_TESTING.md](DESIGN_AND_TESTING.md) for the architecture, implementation decisions, scenario results, limitations, and testing evidence.