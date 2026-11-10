# CSE 491 — AI Agents: Homework 2

**Due:** announced in GitHub Classroom (date and time, Cairo time) · **Work:** individual, unless the course team announces otherwise

## What You're Building

In Homework 1, your experts could only find things by **exact match**. Ask "Find my MSU experience" when the database says "Michigan State University", and the Read Expert's SQL comes back empty. The model has no way to know the two names mean the same place.

In Homework 2 you'll fix that, and make the agent safer at the same time:

- **Search by meaning.** You'll turn your resume records into **embeddings** (lists of numbers that capture meaning) and use them to find records even when the wording is different: abbreviations like "MSU", or categories like "AI skills" when no skill is literally called "AI".
- **Ask before destroying anything.** When a request would delete or overwrite data, the agent will stop, show the user exactly what it's about to do, and only continue after a clear `yes`.

You're building on your own Homework 1 code, with the same stack: Flask, Flask-SocketIO, SQLite and OpenRouter. No Docker, PostgreSQL or extra frameworks needed.

---

## What's Different This Time

Homework 0 and Homework 1 gave you working code for every step. **Homework 2 doesn't.** This README tells you what your agent has to do and how we'll test it, but the code and the design are yours. Several of you asked for more room to make your own decisions, and working things out yourself is how you really learn how these systems fit together.

Some things are the same for everyone, so grading stays fair. Everything else is your call, and you'll explain your choices in a short report.

| The same for everyone | Your choice (explain it in your report) |
|---|---|
| Build on your own HW1, same stack | A new **Semantic Search Expert**, or extend your Read Expert |
| The test scenarios S1–S11 in Step 7 and what they should do | Which fields you embed for each table, and how you combine them |
| The safety rules in Step 5 | Where you store embeddings and when you update them |
| A few things every submission must show (results with scores, a trace, one test command, settings in `.env`) | How the Orchestrator decides between exact SQL and search by meaning |
| The report template | How you store a pending action and match `yes` to it |
| | Your list of allowed database operations, file names, prompts, code structure |

Different designs can all get full marks, as long as they pass the scenarios and you can explain why you built them that way.

---

## How It Works

Here's the general shape. The names in the boxes are just labels; how you actually organize the code is up to you.

```
You (browser)
     |  type a message
     v
Orchestrator
     |  decides what kind of request this is, and which steps to run
     |
     |-- exact question ("How many skills do I have?") --> Database Read Expert --> SQL
     |
     |-- fuzzy question ("Find my MSU experience")  ------> search by meaning
     |        embed the question -> compare with stored embeddings -> ranked matches
     |
     |-- change ("Add Rust to BRAINWORKS")  -------------> Write Expert proposes an allowed operation
     |        safe change (add)          --> runs
     |        destructive change (delete) --> PAUSE: "This will delete ... Reply yes or no"
     v
One clear reply in the chat + a trace in the terminal showing what happened
```

---

## Example Flows

These were traced from a real run of a test version of this homework, so the scores are real numbers. They show the **behavior** we expect, not the code. Your trace and your scores will look different; that's fine, as long as they show the same information.

**Example 1: an abbreviation ("Find my MSU experience")**

```
Orchestrator: wording may not match stored names -> use search by meaning
Search: embed "MSU experience", compare with stored embeddings
     -> institutions #1  "Michigan State University ..."   score 0.60
     -> everything else scores much lower
Reply: "Found it: Michigan State University, Computer Science, East Lansing."
```

**Example 2: two dependent steps ("What did I do at MSU?")**

```
Step 1: search by meaning resolves "MSU" -> "Michigan State University"
Step 2: Database Read Expert uses that exact name in its SQL
     SELECT ... WHERE i.name = 'Michigan State University'
Reply lists the positions found
```

Step 2 only works because it receives step 1's result. That's what "dependent steps" means here.

**Example 3: a destructive request ("Remove Python from CSE 847")**

```
Write Expert proposes: delete_skill(skill_name="Python", experience_name="CSE 847")
This is destructive -> nothing runs yet
Chat: "This will delete skill 'Python' from experience 'CSE 847'. Reply yes or no."
User: no   -> "Cancelled. Nothing was changed."   (database unchanged)
--- later ---
Same request, User: yes -> exactly that one deletion runs, nothing else
```

---

## Project File Map

You're extending your Homework 1 code, not starting over. Copy your working `homework 1/flask_app` and `app.py` into the `homework 2/` folder in your fork, then start from these files:

```
homework 2/
├── app.py                         ← unchanged
├── README.md                      ← UPDATE: setup, run, and how to reset the test data
├── .env.example                   ← NEW: every setting your app needs (names only, no values)
├── DESIGN_AND_TESTING.md          ← NEW: your report (template provided)
│
├── fixtures/                      ← PROVIDED: the course test data
├── tests/                         ← NEW: your one-command scenario tests (Step 7)
│
└── flask_app/
    ├── __init__.py                ← startup: where the database is created and loaded (Step 1)
    ├── utils/
    │   ├── llm.py                 ← Orchestrator and experts; eval() and exec() live here today (Steps 4–5)
    │   ├── socket_events.py       ← chat handler: where a waiting approval can be remembered (Step 5)
    │   └── database.py            ← tables, loading data, queries (Steps 1–3)
    └── database/
        ├── create_tables/         ← add any new tables you decide you need
        └── initial_data/          ← seed CSVs, including llm_roles.csv
```

You'll probably add a file or two of your own (for example, somewhere to keep the embedding code). How you organize it is up to you; just say where things are in your report.

---

## Test Data

In Homework 0 you replaced the sample resume with your own. For Homework 2, the scenarios are graded on the **course test data** in `homework 2/fixtures/`: the original sample resume (Michigan State University, BRAINWORKS, CSE 847, ...) plus a few extra skills such as Machine Learning and Public Speaking. That way everyone's results can be compared.

Your test command (Step 7) should load this test data, for example into a separate test database, so it never touches your own resume. Your own data can stay in your app.

---

## Before You Start: Check Your HW1 (first 2–3 days)

Most HW2 problems start in HW1. Check these four things before writing anything new.

1. **HW1 works.** The app starts, a read question gets an answer, and adding a skill works. Make sure you've applied the two HW1 corrections that were announced (adding `db = current_app.db` in the chat handler, and removing ```` ``` ```` code fences from model output). If your terminal says "Insufficient credits", follow the course announcement about models and credits.
2. **Restart test.** Add a skill, stop the app, start it again. Is the skill still there? In the guided HW1 it isn't, because `createTables(purge=True)` wipes and reloads the database at every start. HW2 needs your data and embeddings to survive a restart.
3. **Find where model output gets executed.** In the guided HW1, the Orchestrator's plan is run with `eval()` and the Write Expert's code is run with `exec()`. Find both lines. Step 5 is about replacing exactly those.
4. **Try one embedding call.** Send one piece of text to the embedding model announced by the course team and print the length of the vector you get back. Check that it isn't all zeros.

If step 1 doesn't work, talk to the TA **in the first week**. Don't wait until the deadline.

---

## Suggested Timeline

Not graded, but it will keep you from getting stuck in the last few days. Bring what's in the right column to the TA session.

| When | Have this ready |
|---|---|
| First TA session after release | The "Before You Start" checks done, plus a short design idea: separate expert or extended Read Expert, what you'll embed, where your approval check will live |
| Middle of week 2 | S1, S2 and S5 working; your approval design decided |
| Last 2–3 days | All scenarios run from one command; report drafted; video recorded |

---

## Building It

The steps below describe what each part has to do. The order is a suggestion.

### Step 1: Keep data across restarts

Make normal startup keep the existing database, and load the initial data only when the database is new (or when you deliberately reset it for testing).

Be careful: just changing `purge=True` to `purge=False` is **not** enough. Try it, then delete a skill that came from the CSV and restart. Then edit `llm_roles.csv` and restart. Watch what happens in both cases, and design your startup so that deleted data stays deleted and prompt edits still take effect.

Document how to reset the **test data** (not your real data) in your README.

### Step 2: Create and store embeddings

- Use the embedding model announced by the course team, through OpenRouter. Read the model name from your `.env`. Don't hard-code it. List every setting your app needs in `.env.example`, with names only and no values.
- Decide which text represents each record. One column, or several combined? For example, "Michigan State University" alone, or the name plus department and city?
- Store the embeddings in SQLite so they survive a restart: for the initial data **and** for records added later through the chat.
- Decide what happens to an embedding when its record is edited or deleted.
- **A failed embedding must never look like a real one.** If the API call fails, or returns an empty or all-zero vector, your code has to notice and report it. Never store it or use it for matching.

### Step 3: Search by meaning

Turn the user's question into an embedding, compare it with your stored embeddings (cosine similarity in plain Python is fine), and return the best matches **ranked**. Each result should include which table it came from, the record's ID, the text that was embedded, and its similarity score. Your HW3 web search will reuse this, so it helps if it can later search other kinds of text too.

Two decisions matter a lot here, and you should base both on real numbers:
- **Which tables to search.** If a question is about skills, should it compare against every table, or only skills?
- **What counts as "no match".** Print the scores for a query that should match and one that shouldn't (e.g. "Harvard" when there's no Harvard in the data), then choose your cut-off. A wrong cut-off returns random records instead of "not found".

### Step 4: Choose the right search, and handle two-step requests

- The Orchestrator decides which kind of search each question needs. Exact questions ("How many skills do I have?", "List all my skills") should still go to the Database Read Expert. Fuzzy ones ("MSU", "AI skills") should use search by meaning. Sending everything to search by meaning doesn't count.
- Support at least one request that needs **two dependent steps**, where the second step uses what the first one found (see Example 2).
- Answers must come from what was actually retrieved. If nothing relevant was found, the agent says so.

### Step 5: Ask before destructive changes, and make the check impossible to skip

**The conversation:**
- When a request would delete, overwrite or otherwise destroy data, **don't run it yet.** Show the user exactly what will happen ("This will delete skill 'Python' from experience 'CSE 847'").
- `no` → cancel, change nothing.
- `yes` → run **exactly the action you showed**, and nothing else. Don't send the original message back to the model, because it might produce a different action the second time.
- Anything else ("maybe", "hmm") → nothing runs and nothing gets approved. You decide whether to ask again or cancel; write your rule in the report.
- If the user moves on to a different request instead of answering, a later `yes` must not approve the old action.

**Where the check lives:** a confirmation message in the chat isn't real protection if some other code path can still delete data without it. Put the approval check **in the code that actually performs the write**, so no expert and no wording can get around it. "Clean up my skills so the list is empty" contains none of the obvious words like "delete" or "remove", and it must still be stopped (scenario S9).

**Replace `eval()` and `exec()`:**
- Make a small list of database operations your agent is allowed to perform (for example: add a skill, delete a skill by name, delete all skills). The Write Expert's job becomes **choosing one operation and filling in its values**, usually as JSON. Your code checks the operation name and every value before anything runs.
- Read the Orchestrator's plan as data (for example JSON with `json.loads`) and check it, e.g. reject unknown expert names. Never pass model output to `eval()`.
- If model-generated code still runs anywhere in your app, you must show that it can't perform a destructive change without approval (S9). The easiest way is not to execute generated code at all.

Test deletions only on the test data. Show the database before and after both a `no` and a `yes`.

### Step 6: Show what happened (the trace)

For every message, print or log a short trace showing: an ID for the request, the route chosen and a one-line reason, which experts or operations ran, the approval state (none / waiting / approved / cancelled), and the outcome. The format is up to you: terminal, log file or a panel in the page. Never print your API key.

### Step 7: Test it

Provide **one command** (for example `python tests/run_scenarios.py`) that runs these scenarios on the test data and prints each ID with PASS or FAIL. Scenarios that need the real API can be marked as such. For S10, find a way to make the embedding call fail without breaking your real key, e.g. a wrong key or model name set just for the test.

| ID | Try | What should happen |
|---|---|---|
| **S1** | `Find my MSU experience` | Michigan State University is among the top results; scores visible in the trace |
| **S2** | `What AI skills do I have?` (no skill name contains "AI") | AI-related skills such as Machine Learning come back; an unrelated skill (Public Speaking) doesn't, or ranks lower |
| **S3** | `List all my skills` or `How many positions do I have?` | Goes to the Database Read Expert, not search by meaning; the trace says why |
| **S4** | `What did I do at MSU?` | Two steps: resolve the name, then look it up; both visible in the trace |
| **S5** | Add a skill through the chat, then restart the app | The skill and its embedding are still there, and a search by meaning finds it |
| **S6** | A deletion request, then `no` | The exact action is shown; `no` leaves the database unchanged |
| **S7** | The same deletion request, then `yes` | Only the action that was shown runs |
| **S8** | A deletion request, then `maybe`; separately, change the subject before answering | Nothing runs and nothing is approved; behavior matches the rule in your report |
| **S9** | `Clean up my skills so the list is empty` | Paused for approval even though no "danger word" was used |
| **S10** | Make the embedding call fail | A clear error; no made-up or zero-vector match; the app still works afterwards |
| **S11** | `Find my Harvard experience` (not in the data) | "Not found"; no invented record |

---

## Bonus: ReAct Orchestration (optional, up to +10 points)

So far your Orchestrator can plan all its steps at the start. In lecture we saw **ReAct**, where the agent works in a loop: it thinks about what it needs (**Thought**), does one thing (**Action**), looks at the result (**Observation**), and only then decides the next step. The original version of this homework requires a ReAct orchestrator; here it's a bonus.

To earn it, make your Orchestrator work in that loop:

1. **Thought:** the model says in one line what it needs next.
2. **Action:** it picks one expert or search, or decides it's done.
3. **Observation:** your code runs the action and gives the result back to the model.
4. Repeat until it's done, or until a **maximum number of rounds** that you choose (for example 5).

The same safety rules apply inside the loop: every action is checked before it runs, deletions still need `yes`, and no `eval()`/`exec()`. Your trace should show the Thought, Action and Observation of every round.

| ID | Try | What should happen |
|---|---|---|
| **R1** | `What AI skills do I have, and in which experiences did I use them?` | The trace shows the agent seeing the skills first, then choosing a follow-up lookup based on them |
| **R2** | `What did I do at Harvard?` | The loop stops (done or round limit) with an honest "not found", no endless loop |
| **R3** | A deletion request handled inside the loop | It still pauses for `yes` exactly like S6/S7 |

In your report, explain the round limit you chose, and one case where planning everything up front works better than ReAct (or the other way round).

---

## Things That Commonly Go Wrong

We built and tested a version of this homework on the guided HW1, against a real model, before writing this up. These problems came up, and you'll likely meet some of them too:

- **Data comes back after a restart, or prompt edits stop working.** This is the `purge=False` problem from Step 1. Decide what should load once and what should reload at every start.
- **"Sorry, I couldn't plan a response to that."** Check the terminal. It's usually the model wrapping its answer in ```` ``` ```` code fences, or an API error such as "Insufficient credits".
- **S2 returns experiences instead of skills.** Experiences that mention "AI" in their description can push the actual skills out of the top results. Think about which tables a skills question should search.
- **"Harvard" matches something random.** Your "no match" cut-off is too low. Look at real scores before choosing it.
- **New rows merge into the last line of a CSV.** The seed CSV files don't end with a newline, so put each row you add on its own line.

---


## Your Design and Testing Report

Add a file called `DESIGN_AND_TESTING.md` to the root of your HW2 folder, using the template provided. Write it in your own words; short and specific beats long and generic. It must include:

1. A simple diagram of your system and what changed from HW1.
2. At least **three** real decisions you made: what the options were, what you chose, the trade-off, and what would make you choose differently.
3. At least **five** of the scenarios above (including at least one failure) with what you expected, what actually happened, and the evidence.
4. Two limitations that are still there, and how you'd improve them.
5. What you wrote or changed yourself, and what help you used (libraries, documentation, AI tools).

---

## Getting Help

| The TA can help you with | The TA won't |
|---|---|
| Understanding embeddings, cosine similarity, approval flows, ReAct | Write HW2 code or prompts for you |
| Debugging Python, SQLite and OpenRouter errors | Give you a full or sample solution |
| Reviewing your design idea before you build it | Choose your design for you |
| Explaining the scenarios and the rubric | Grade drafts before the deadline |

You may use AI tools according to the course policy, but say so in your report, and make sure you can explain every part of your code. You'll be asked to.

---

## Submitting

Push your work to your fork:

```bash
cd "homework 2"
git add .
git commit -m "Homework 2"
git push origin main
```

Your `homework 2` folder must contain your code, an updated README with setup and run steps (including how to reset the test data), `.env.example`, `DESIGN_AND_TESTING.md`, and your `tests/` folder with the one test command.

Then record a demo video (see `documentation/rubric.md` for exactly what to show) and submit **both** of the following via the course submission form:

1. Your demo video
2. Your fork's GitHub URL (e.g. `https://github.com/YOUR-USERNAME/ai-agents`)

**Live check.** After the deadline you'll run your app in front of the TA or instructor for about 5–7 minutes: one or two scenarios with wording you haven't seen before, a look at your trace, and one or two questions about your choices.
