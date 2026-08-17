# Current Task — Complete Shelfie Initial Project Setup

## Objective

Complete the initial development setup for the Shelfie take-home assignment so that both the frontend and backend are correctly scaffolded, all baseline dependencies required for development are installed, and both sides can be run successfully.

This task is **setup only**. Do not implement the bookshelf AI pipeline, catalog matching, persistence features, or production UI yet.

Before making changes, read the repository-root `AGENTS.md` and follow it.

---

## Current Environment

Repository:

```text
/Users/john/dev/mealvue_assignment/shelfie
```

Machine:

```text
macOS
Intel x86_64
```

Already installed globally:

```text
Node.js v22.23.1
npm 10.9.8
Python 3.14.3
Python 3.12.14
```

For this project, the backend must use:

```text
Python 3.12.14
```

because the local computer-vision portion may later depend on libraries with better Intel macOS/Python 3.12 compatibility.

An existing virtual environment has already been created at:

```text
backend/.venv
```

It currently resolves to:

```text
/Users/john/dev/mealvue_assignment/shelfie/backend/.venv/bin/python
```

Do **not** delete or recreate the virtual environment unless it is actually broken.

---

## Required Project Stack

The take-home assignment requires:

### Frontend
- React Native
- Expo
- TypeScript

### Backend
- Python 3.12
- Django 5.2.x
- Django REST Framework
- SQLite

### Later AI Work
- pretrained local computer-vision model
- CPU inference
- hosted vision-language model

Do not implement the AI portion in this task.

---

# Tasks

## 1. Inspect Existing Repository State

From:

```text
/Users/john/dev/mealvue_assignment/shelfie
```

inspect:

```bash
pwd
git status
git branch --show-current
ls -la
find . -maxdepth 2 -type f | sort
```

Do not overwrite existing files blindly.

Confirm whether these already exist:

```text
AGENTS.md
.gitignore
frontend/
backend/
backend/.venv/
```

Preserve valid existing work.

---

## 2. Configure `.gitignore`

Ensure the repository-root `.gitignore` excludes at least:

```gitignore
# macOS
.DS_Store

# Python
__pycache__/
*.py[cod]
backend/.venv/
backend/db.sqlite3
backend/media/

# Environment variables / secrets
.env
*.env

# Node / Expo
node_modules/
.expo/
dist/
web-build/

# IDE
.vscode/
.idea/
```

If `.gitignore` already exists, merge these rules into it instead of replacing unrelated existing rules.

Verify that `.venv`, `node_modules`, local database files, and secrets are not tracked by Git.

---

## 3. Complete Backend Setup

Work inside:

```text
backend/
```

Activate the existing environment:

```bash
source .venv/bin/activate
```

Verify:

```bash
python --version
which python
```

Expected Python:

```text
Python 3.12.14
```

Expected interpreter path should point into:

```text
backend/.venv/bin/python
```

Upgrade pip inside the virtual environment:

```bash
python -m pip install --upgrade pip
```

Install the baseline backend dependencies:

```bash
python -m pip install "Django>=5.2,<5.3" djangorestframework Pillow django-cors-headers python-dotenv
```

Why these are included:

- `Django`: backend framework
- `djangorestframework`: REST API framework
- `Pillow`: image loading/validation needed for bookshelf uploads
- `django-cors-headers`: local Expo-to-Django development requests
- `python-dotenv`: local environment-variable loading for future hosted-model API keys

Do **not** install computer-vision frameworks such as PyTorch, Ultralytics, Transformers, OpenCV, or hosted AI SDKs yet. Those dependencies depend on the model/provider decision and should not be selected during generic setup.

---

## 4. Scaffold Django Project If Needed

Inside `backend/`, the desired structure is:

```text
backend/
├── .venv/
├── manage.py
├── requirements.txt
├── config/
└── library/
```

If `manage.py` and `config/` do not exist, create the project in the current directory:

```bash
django-admin startproject config .
```

If the `library` Django app does not exist, create it:

```bash
python manage.py startapp library
```

Do not create unnecessary Django apps.

---

## 5. Configure Django

In `backend/config/settings.py`, ensure these applications are registered:

```python
"rest_framework",
"corsheaders",
"library",
```

Ensure `corsheaders.middleware.CorsMiddleware` is placed appropriately in `MIDDLEWARE`, before Django's `CommonMiddleware`.

For local development only, configure CORS so the Expo development client can call the backend without unnecessary friction.

Prefer a simple development configuration appropriate for a take-home assignment. Do not build a complicated environment system.

Keep SQLite as the database.

Do not add PostgreSQL.

---

## 6. Run Django Initialization

Run:

```bash
python manage.py migrate
python manage.py check
```

The Django system check must pass.

Then verify the development server starts:

```bash
python manage.py runserver
```

Confirm that:

```text
http://127.0.0.1:8000/
```

responds successfully.

Stop the server after verification.

Do not leave background processes running.

---

## 7. Save Backend Dependencies

Generate:

```text
backend/requirements.txt
```

using the active Python 3.12 virtual environment:

```bash
python -m pip freeze > requirements.txt
```

Verify that it does not contain unrelated packages from the global Python installation.

---

## 8. Scaffold Frontend

Return to the repository root.

Desired structure:

```text
frontend/
```

If the Expo project does not already exist, create it using the current Expo project generator with TypeScript support.

Use the normal Expo scaffold rather than manually constructing a React Native project.

The frontend must use:

```text
React Native
Expo
TypeScript
```

Do not create a plain React web application.

Do not use Flutter.

Do not replace Expo with bare React Native.

---

## 9. Install Baseline Frontend Dependencies

Install the Expo-supported packages needed for the first product flow:

```text
expo-image-picker
expo-camera
```

Use:

```bash
npx expo install <package>
```

rather than forcing arbitrary npm versions for Expo-managed native packages.

Do not install large UI frameworks or unnecessary state-management libraries.

Do not add Redux, Zustand, NativeWind, or other architecture unless a concrete need appears later.

The goal is a minimal, understandable frontend.

---

## 10. Verify Expo

Run Expo's project checks if available for the generated SDK, then start the development server:

```bash
npx expo start
```

Verify that Metro/Expo starts without dependency errors.

If an emulator or simulator is already available, a successful app launch is useful, but do not spend significant time repairing unrelated emulator problems during this setup task.

Stop the Expo process after verification.

---

## 11. Environment Variable Template

Create a repository-root or backend-level `.env.example` appropriate to the chosen project structure.

It should contain placeholders only, for example:

```env
VISION_API_KEY=
```

Do not create or commit real credentials.

Do not choose the hosted VLM provider during this setup task unless one has already been explicitly selected elsewhere in the repository.

---

## 12. Do Not Implement Features Yet

Do **not** implement any of the following in this task:

- bookshelf image analysis
- book-spine detection
- OCR
- VLM calls
- catalog generation
- fuzzy matching
- confidence scoring
- review workflow
- library CRUD
- AI-specific API endpoints
- production UI
- authentication
- deployment
- Docker
- Redis
- Celery
- PostgreSQL
- cloud infrastructure

This task should leave us with a clean foundation, not prematurely build the assignment.

---

# Target Repository State

At completion, the repository should roughly look like:

```text
shelfie/
├── .gitignore
├── .env.example
├── AGENTS.md
├── codex_docs/
│   └── current_task.md
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   └── ...
└── backend/
    ├── .venv/                  # ignored
    ├── manage.py
    ├── requirements.txt
    ├── config/
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    └── library/
        ├── migrations/
        ├── __init__.py
        ├── admin.py
        ├── apps.py
        ├── models.py
        ├── tests.py
        └── views.py
```

Exact Expo-generated files may vary by SDK version. Do not fight the framework-generated structure merely to match this diagram.

---

# Verification Checklist

Before declaring the task complete, verify all of the following:

- [ ] Repository remains on the intended branch.
- [ ] Existing work was preserved.
- [ ] `backend/.venv` uses Python 3.12.
- [ ] Django 5.2.x is installed.
- [ ] Django REST Framework is installed.
- [ ] Pillow is installed.
- [ ] CORS support is installed/configured for local development.
- [ ] Django project exists.
- [ ] `library` Django app exists.
- [ ] SQLite remains configured.
- [ ] `python manage.py migrate` succeeds.
- [ ] `python manage.py check` succeeds.
- [ ] Django development server starts.
- [ ] `backend/requirements.txt` exists.
- [ ] Expo React Native frontend exists.
- [ ] Frontend uses TypeScript.
- [ ] Expo dependencies install successfully.
- [ ] `npx expo start` starts successfully.
- [ ] `.gitignore` excludes generated/local/secrets files.
- [ ] `.env.example` contains placeholders only.
- [ ] No AI implementation has been added.
- [ ] No unnecessary infrastructure has been added.
- [ ] No real secrets are committed.

---

# Git Rules

Do not commit automatically unless explicitly instructed to do so.

Do not push automatically.

Do not rewrite Git history.

At the end, show the user the exact files changed and recommend a meaningful commit message.

Suggested commit message if the user approves:

```text
chore: scaffold Expo frontend and Django backend
```

---

# Final Report

When finished, report concisely:

## Completed
What was installed and created.

## Verification
Commands/tests that succeeded.

## Files Changed
List the important files created or modified.

## Issues
Any failures, warnings, compatibility concerns, or setup pieces intentionally deferred.

## Next Recommended Task
Recommend the smallest next development task.

Do not claim something works unless it was actually executed and verified.
