# Agent Instructions

This repository contains three applications:

- frontend/ — web frontend
- backend/ — API/backend service
- mobile/ — Mobile application

## Rules

1. Read this file before making changes.

2. Before working in a directory, read the nearest AGENTS.md.
   More specific instructions override this file.

3. Frontend code belongs in frontend/.
   Backend code belongs in backend/.
   Mobile app code belong to mobile/.

4. Do not move business logic between frontend and backend.
   The backend owns authentication verification, business rules,
   orders, payments, stock, and persistence.
   The frontend consumes the backend API.

5. Do not duplicate backend business rules in the frontend.
   Client-side validation may improve UX, but the backend is authoritative.

6. Changes affecting the API contract must be coordinated between
   frontend/ and backend/.

7. Do not invent requirements or make product decisions that are not
   documented in the applicable specification. Ask when a required
   decision is missing.

8. Keep changes scoped to the task. Do not add frameworks, services,
   features, or infrastructure without explicit approval.

9. Never commit secrets, credentials, tokens, or environment files.
   Use environment variables and provide/update .env.example files
   when configuration changes.

10. Keep frontend and backend independently testable and runnable.

## Application-specific instructions

Backend:
Read backend/AGENTS.md before modifying backend code.

Frontend:
Read frontend/AGENTS.md before modifying frontend code, when it exists.

## Git

* Commit every meaningful, working change.
* Keep each commit focused on one logical change.
* Do not include unrelated files.
* Use Conventional Commits: `<type>: <description>`.
* Use types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
* Use lowercase, imperative descriptions with no trailing period.
* Never push, force-push, reset with `--hard`, or rewrite history.
* After each commit, report the commit hash and what was committed.

## Completion

Before finishing:

* Verify the requested behavior.
* Check relevant edge cases.
* Run required checks.
* Update relevant documentation or specification when necessary.

Final reports should briefly state:

* What changed
* Checks performed
* Known limitations