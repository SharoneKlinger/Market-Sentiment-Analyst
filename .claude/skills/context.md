---
name: context
description: >
  Deep context loader. Use /context to load full project state, architecture,
  recent changes, open tasks, and lessons learned. Use at session start or
  when you need to reorient on the project.
---

# Context Loader

Load and internalize the full project context.

## Steps

1. **Read project guidelines:**
   - Read `CLAUDE.md` for behavioral rules
   - Read `autoresearch/program.md` for experiment framework

2. **Understand the codebase:**
   - Read `app.py` — the main Flask application
   - Read `requirements.txt` — dependencies
   - Read `README.md` — project overview
   - Scan for any new files or changes since last session

3. **Load task state:**
   - Read `tasks/todo.md` — current tasks and progress
   - Read `tasks/lessons.md` — past mistakes and patterns to avoid

4. **Check git state:**
   - `git status` — any uncommitted work?
   - `git log --oneline -10` — recent commit history
   - `git branch -a` — active branches
   - `git diff` — any pending changes?

5. **Check environment:**
   - Verify environment variables are set (ALPACA_API_KEY, etc.)
   - Verify autoresearch submodule is initialized
   - Check if any tests exist and their status

6. **Summarize to user:**
   - Current branch and last commit
   - Any uncommitted changes
   - Open tasks from todo.md
   - Key lessons to remember
   - Ready state: what's next?

## Output
Provide a concise project status briefing after loading context.
