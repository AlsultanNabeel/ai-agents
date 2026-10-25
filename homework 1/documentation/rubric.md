# CSE 491 — AI Agents: Homework 1 Rubric

This assignment is graded on a 100 point scale. All grading is based on your demo video.

## Functional Requirements


| #   | Requirement                                                                                                          | Points | How to demonstrate                                                                                                                                                                                           |
| --- | -------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Database Read Expert** — ask a question like "How long did they work at [institution]?"                            | 20     | Show the console printing the generated SQL query, and the chat replying with an accurate answer                                                                                                             |
| 2   | **Database Write Expert** — ask to add a skill, e.g. "Add [skill] to [experience]"                                   | 20     | Show the console printing the generated Python code, the skill appearing on the resume page right after the AI responds, and it still being there after you manually reload the page                         |
| 3   | **Orchestrator Coordination** — ask a compound request, e.g. "Does he know [skill]? If not, add it to [experience]." | 20     | Show the console printing the Orchestrator's plan, that the plan includes both a Database Read Expert call and a Database Write Expert call in the right order, and that both actually execute in that order |
| 4   | **Database Schema** — the `llm_roles` table                                                                          | 20     | Show, via a query or a database browser, that `llm_roles` exists and contains all four expert configurations (Database Read Expert, Database Write Expert, Content Expert, Orchestrator)                     |
| 5   | **Concept Question** — Explain 3 different prompt engineering concepts that you tried and their effectiveness        | 20     | Add a file called `prompt_engineering.md`                                                                                                                                                                    |




## Grading Policy

- Each requirement uses **all-or-nothing** grading. You receive the full points or zero — no partial credit.
- Points are awarded based on **functionality demonstrated in the video**, not code quality or implementation choices.
- Even if your app works perfectly, you receive **zero points** for any requirement not clearly shown in your video.



## Demo Video Structure

- State your full name at the start
- Say: *"I will now demonstrate the functional requirements for CSE 491 Homework 1"*
- Announce each requirement before demonstrating it
- Keep the console/terminal visible on screen for requirements 1–3 — the graded output includes what gets printed there
- Clear audio and video required



## Submission Checklist

- [ ] `llm.py` has the master template, `fill_template`, and all four expert-routing functions
- [ ] `database.py` has `getLLMRoles()` and `insertRows()`
- [ ] `llm_roles` table created and seeded with all four expert configs
- [ ] Chat now routes through the Orchestrator by default
- [ ] Resume panel refreshes automatically after a database write
- [ ] Code pushed to your fork: `git push origin main`
- [ ] Fork URL included in your submission (e.g. `https://github.com/YOUR-USERNAME/ai-agents`), **OR** the URL of your Pull Request (PR) on your team lead's repository. So the grader can access your code
- [ ] Demo video recorded and uploaded via the [homework submission form](https://docs.google.com/forms/d/e/1FAIpQLSdWGZAuyNQO-O1c6cfPUJs_cmJPy-neG1_GyDCjD56bGVod6w/viewform)