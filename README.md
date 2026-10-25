# Welcome to the AI Agents Course

This course is to help you understand the fundamentals to making Agentic workflows. 

All course materials are available in this repository. You can also find the course materials on [Google Classrooms](https://classroom.google.com/c/ODg1MTY5ODAzNjg4?cjc=7zlurwtm).

Please use the community whatsapp group to ask questions and share your learnings.

## Getting the code

Instead of cloning this repo directly, **fork it** into your own GitHub account
(click **Fork** at the top of this page), then clone your fork locally:

```bash
git clone https://github.com/YOUR-USERNAME/ai-agents
cd ai-agents
```

All your work happens in your own fork — you don't need push access to this
repo. You'll reuse this same fork for every homework released throughout the
course, so you only need to do this once.

### Staying up to date with new homeworks

Add this repo as an `upstream` remote so you can pull in new homeworks as
they're released:

```bash
git remote add upstream https://github.com/AUC-SPOCS-AI-AGENTS/ai-agents
```

When a new homework is released, pull it into your fork with:

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

Since each homework lives in its own folder, this should merge cleanly. If you
hit a conflict, it means you edited a file that was also updated upstream —
resolve it by keeping your changes and re-adding the new content, then commit.

## One-time environment setup

Right after cloning your fork, run the setup script from the repo root:

```bash
bash setup.sh
```

This creates a single Python virtual environment (`venv/`) and installs
`requirements.txt` at the repo root — shared across every homework, so you
only do this once. Each homework's own README (e.g. `homework 0/README.md`)
covers how to run that specific app.

## Important links

- [Google Classrooms](https://classroom.google.com/c/ODg1MTY5ODAzNjg4)
- [Github](https://github.com/AUC-SPOCS-AI-AGENTS/ai-agents)

