# CSE 491 — AI Agents: Homework 0

## What You're Building

By the end of this assignment, you'll have a **personal AI agent** running on your laptop — a web application that displays your resume and lets you (or anyone) chat with an AI assistant that has read your resume and can answer questions about it.

This is your starting point. In future homeworks, you'll add memory, tools, and more sophisticated behaviors to this same agent. The goal of Homework 0 is simply to get it running and to start understanding how the pieces connect.

---

## How It Works

Here's the flow when you type a message in the chat:

```
You (browser)
     |  type a message → JavaScript emits 'send_message' over WebSocket
     v
Flask + Socket.IO    (flask_app/utils/socket_events.py)
     |  reads your resume from the database
     |  builds a system prompt: "You are reviewing this resume: ..."
     |  sends your message + system prompt to OpenRouter
     v
OpenRouter API  ──►  GPT-3.5
     |  AI generates a response
     v
Flask emits 'receive_message' back over WebSocket
     |
     v
JavaScript displays the reply in the chat panel — no page reload
```

**Two kinds of communication** are happening in this app:
- **HTTP** (regular web): when you visit `/resume`, your browser requests a page and gets HTML back. The connection closes.
- **WebSocket** (real-time): the chat panel keeps an *open connection* to the server. Messages flow instantly in both directions without reloading the page.

---

## Project File Map

```
ai-agents/                          (repo root)
├── setup.sh                        ← one-time setup script (shared across homeworks)
├── requirements.txt                ← Python packages, shared across homeworks
├── .env.example                    ← template for your API key
│
└── homework 0/
    ├── app.py                      ← START HERE: runs the web server
    │
    └── flask_app/
        ├── __init__.py             ← creates the Flask app, connects everything
        ├── routes.py               ← defines URL paths (/, /resume)
        │
        ├── utils/
        │   ├── llm.py              ← talks to the OpenRouter AI API
        │   ├── socket_events.py    ← handles real-time chat messages
        │   └── database.py         ← reads/writes the SQLite database
        │
        ├── templates/
        │   ├── layout.html         ← shared nav bar and page structure
        │   ├── home.html           ← your bio page  ← EDIT THIS
        │   └── resume.html         ← resume display + chat panel
        │
        ├── static/
        │   ├── css/style.css       ← all styling for the app
        │   └── images/headshot.png ← your profile photo  ← REPLACE THIS
        │
        └── database/
            ├── create_tables/      ← SQL files that define the database schema
            └── initial_data/       ← CSV files with your resume data  ← EDIT THESE
```

**Suggested reading order for understanding the code:**
1. `routes.py` — see how URLs map to Python functions
2. `socket_events.py` — see how the chat flow works
3. `llm.py` — see exactly what an LLM API call looks like
4. `database.py` — see how data is stored and retrieved
5. `templates/resume.html` — see how the frontend connects to all of the above

---

## Setup

> Before starting, ensure that the repo is forked into your own GitHub account
> and cloned locally — see the "Getting the code" section in the
> [root README](../README.md) if you haven't done this yet.

### Step 1: Run the setup script

`setup.sh`, `requirements.txt`, and `.env` all live at the **repo root**, not
inside `homework 0/` — this venv is shared across every homework in the
course, so you only run this once, right after cloning:

```bash
bash setup.sh
```

This script will:
- Check that Python 3 is installed
- Create a virtual environment (`venv/`) at the repo root
- Install all required packages
- Create your `.env` file from the template

Future homeworks may add new packages to `requirements.txt` — if `pip` errors
about a missing package after pulling a new homework, just re-run
`bash setup.sh` to pick up the new dependencies.

> **What is a virtual environment?**
> A `venv` is an isolated Python installation just for this project. It keeps
> this project's packages separate from other Python projects on your machine.
> Think of it as a clean sandbox.

### Step 2: Add your OpenRouter API key

Open the `.env` file that was just created and replace the placeholder:

```
OPENROUTER_API_KEY=paste-your-key-here
```

Paste the shared API key we sent you. Keep it private — never
commit the `.env` file to git (it's already in `.gitignore`, so git will
ignore it automatically).

> **Why a .env file?**
> Putting a secret key directly in your code is dangerous — anyone who reads
> your code (or your git history) would have your key. The `.env` file keeps
> secrets separate from code.

### Step 3: Activate the virtual environment

Every time you open a new terminal to work on this project, you need to activate
the virtual environment (from the repo root) so Python uses the right packages:

```bash
# On Mac / Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

You'll know it's active when you see `(venv)` at the start of your terminal prompt.

### Step 4: Run the app

With the venv activated, `cd` into this homework's folder and run its app:

```bash
cd "homework 0"
python app.py
```

You should see:
```
Starting AI Resume Agent...
Open your browser to: http://localhost:8080
Setting up database...
  Loaded data for table: institutions
  ...
Database ready.
```

Open your browser and go to **http://localhost:8080**.

---

## Customizing Your Resume

The resume data lives in CSV files. Each file corresponds to one database table:

| File | What it stores | Example |
|------|----------------|---------|
| `initial_data/institutions.csv` | Places you've worked or studied | Michigan State University |
| `initial_data/positions.csv` | Job titles at each institution | Instructor, Researcher |
| `initial_data/experiences.csv` | Specific projects or achievements | CSE 491 — AI Agents |
| `initial_data/skills.csv` | Technical skills and proficiency levels | Python (10/10) |

**To update your resume:**
1. Edit the CSV files with your own information
2. Restart the app (`Ctrl+C` to stop, then `python app.py` again)
3. Visit `/resume` — the AI will now know your updated resume

**To update your bio and photo:**
- Edit `flask_app/templates/home.html` — look for the `NOTE:` comments
- Replace `flask_app/static/images/headshot.png` with your own photo (keep the same filename, or update the path in `home.html`)

---

## Understanding the Code

Once the app is running, open each file in the suggested reading order above.
Look for these markers throughout the code:

| Marker | Meaning |
|--------|---------|
| `# NOTE:` | Something you're expected to modify or extend |
| `# QUESTION:` | A concept worth thinking about — you may be asked about these |
| Docstrings (`"""..."""`) | Explain what a function does and why |
| Inline comments (`#`) | Explain the *why* behind a line of code |

---

## Questions to Think About

These connect the code to the broader course themes. You don't need to submit
answers for Homework 0, but future assignments will build on them:

1. **What makes this an "AI agent" rather than just a chatbot?**
   The AI has access to your resume (a knowledge base) and uses it to answer
   questions. What else would you need to add to make it more autonomous?

2. **What does the system prompt do, and why does it matter?**
   Find `build_resume_system_prompt()` in `socket_events.py`. How would
   the AI's behavior change if you modified the instructions in that function?

3. **The AI has no memory between messages. What would change if it did?**
   Right now, each message is independent. If you ask "What year did I start
   at MSU?" and then ask "What did I do there?" — the AI doesn't know what
   "there" refers to. How would you fix this?

4. **What is the difference between HTTP and WebSockets?**
   Find the two types of communication in `resume.html` and trace how
   each one works.

5. **Where is your API key, and why is it stored there?**
   What would happen if you committed your `.env` file to git? Try to find
   if any real API keys have been accidentally committed in public repos
   on GitHub — this is a very common security mistake.

---

## Submitting

When you're ready to submit, push your work to your fork:

```bash
git add .
git commit -m "Homework 0"
git push origin main
```

Then record a short demo video showing:
1. The app running (`python app.py` and the browser at `localhost:8080`)
2. Your customized resume page with your own data
3. A chat interaction where the AI answers a question about your resume

Submit **both** of the following using the [course submission form](https://classroom.google.com/c/ODg1MTY5ODAzNjg4):
1. Your demo video
2. Your fork's GitHub URL (e.g. `https://github.com/YOUR-USERNAME/ai-agents`) so the grader can view your code
