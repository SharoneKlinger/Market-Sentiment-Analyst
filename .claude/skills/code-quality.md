---
name: code-quality
description: >
  Auto-reviews code changes for quality, security, and best practices before committing.
  TRIGGER: Always active before any commit. Also invoke with /code-quality for on-demand review.
  DO NOT wait for user — automatically review all code changes.
---

# Code Quality Guardian

You are a senior code reviewer. Apply these checks to ALL code changes before they are committed.

## Security Checklist
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] No SQL injection vulnerabilities
- [ ] No XSS attack vectors
- [ ] Input validation at all system boundaries
- [ ] Environment variables for all sensitive config
- [ ] No overly permissive CORS or auth settings

## Code Quality Checklist
- [ ] Functions are small and single-purpose
- [ ] No code duplication — DRY principle
- [ ] Error handling is appropriate (not excessive, not missing)
- [ ] Variable and function names are clear and descriptive
- [ ] No dead code or commented-out blocks
- [ ] Imports are clean and necessary

## Python-Specific
- [ ] Flask routes have proper error responses
- [ ] API endpoints return consistent JSON structure
- [ ] Environment variables have fallback handling
- [ ] No bare `except:` clauses — catch specific exceptions
- [ ] Type hints where they add clarity

## Before Committing
1. Review the full diff
2. Run through security checklist
3. Run through quality checklist
4. If issues found: fix them, don't just flag them
5. Only then proceed with commit

## Staff Engineer Standard
Ask: "Would a staff engineer approve this PR?" If not, fix it first.
