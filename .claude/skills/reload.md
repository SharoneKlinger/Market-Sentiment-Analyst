---
name: reload
description: >
  Full session reload. Use /reload to re-initialize everything: submodules, context,
  tasks, lessons, and all active skills. Use when starting a new session, after
  context compaction, or when you feel disoriented.
---

# Reload — Full Session Re-initialization

Perform a complete reload of all project context and state.

## Reload Sequence

### Step 1: Initialize Environment
```bash
git submodule update --init --recursive
```

### Step 2: Load All Project Files
Read these files in order:
1. `CLAUDE.md` — behavioral guidelines and rules
2. `autoresearch/program.md` — experiment framework
3. `app.py` — main application code
4. `requirements.txt` — dependencies
5. `README.md` — project overview

### Step 3: Load Task State
1. `tasks/todo.md` — current task list and progress
2. `tasks/lessons.md` — accumulated lessons and patterns

### Step 4: Check Git State
- Run `git status` for uncommitted changes
- Run `git log --oneline -10` for recent history
- Run `git branch` for current branch
- Run `git diff` for pending changes

### Step 5: Verify Skills Active
Confirm these skills are loaded and available:
- `/autoresearch-oversight` — experiment loop oversight
- `/market-sentiment` — market data analysis
- `/code-quality` — code review guardian
- `/context` — deep context loader
- `/brainstorm` — creative ideation
- `/reload` — this skill

### Step 6: Report Status
Output a brief status report:
- Current branch and last commit
- Uncommitted changes (if any)
- Open tasks count
- Key lessons to remember this session
- Skills loaded and ready

## When to Use
- Start of every new session
- After context compaction
- When you feel lost or disoriented
- After major branch switches
- When the user says "reload" or "reset context"
