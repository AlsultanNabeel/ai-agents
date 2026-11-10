# Homework 2: Search by Meaning and Safe Changes

An AI resume agent (Flask, Flask-SocketIO, SQLite, OpenRouter) that finds resume records by meaning using embeddings, and asks for a `yes` before it deletes anything.

The design decisions and test results are in [DESIGN_AND_TESTING.md](DESIGN_AND_TESTING.md).

## Setup

From the repo root, once:

```bash
bash setup.sh
source venv/bin/activate
```

Then put your values in the `.env` file at the repo root. These are the settings the app needs (also listed in [.env.example](.env.example)):

| Setting | What it is |
|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `EMBEDDING_MODEL` | Embedding model on OpenRouter, e.g. `nvidia/nemotron-3.5-embed-8b:free` |
| `SEARCH_MIN_SCORE` | Optional. Lowest similarity score that counts as a match. Defaults to `0.15` |

## Run the app

```bash
cd "homework 2"
python app.py
```

Open http://localhost:8080. On the first start the app creates the database and embeds every record, so it takes a little longer. Later starts keep the existing data and only embed new or changed records.

## Run the tests

```bash
cd "homework 2"
python tests/run_scenarios.py
```

This runs scenarios S1–S11 on the course test data in `fixtures/` and prints PASS or FAIL for each one. Every scenario calls OpenRouter, so they all need a working `.env`. It takes a few minutes.

## Reset the test data

The test command rebuilds its own database, `tests/test_resume.db`, from `fixtures/` every time it runs, so the test data is reset automatically. To reset it by hand, delete that file:

```bash
rm "homework 2/tests/test_resume.db"
```

This never touches your real resume data in `flask_app/database/resume.db`.

## Reset your own data (optional)

Delete `flask_app/database/resume.db` and start the app. It reloads everything from `flask_app/database/initial_data/` and embeds it again.

Editing a prompt in `flask_app/database/initial_data/llm_roles.csv` needs no reset: prompts reload from the CSV at every start.
