# AGENTS.md

## Project Overview

**Shelfie** is a take-home assignment for MealVue's **Full Stack Developer — AI & Computer Vision** role.

The app turns a bookshelf photo into a structured personal library.

The intended flow is:

1. User takes or selects a bookshelf photo in the mobile app.
2. The photo is uploaded to the Django REST API.
3. A pretrained **local computer-vision model** running on CPU detects individual book spines.
4. Detected spine crops are sent to a **hosted vision-language model (VLM)** to read title and author.
5. The extracted title/author are matched against `catalog.csv`.
6. Each match receives a confidence score.
7. High-confidence matches may be accepted directly.
8. Low-confidence or unmatched results must be shown to the user for review.
9. Confirmed books are persisted to the user's library.

The assignment is intentionally scoped to roughly **8 hours of implementation work**. Prefer a small, working, explainable system over a large or over-engineered one.

---

## Non-Negotiable Stack

### Frontend
- React Native
- Expo
- TypeScript preferred

### Backend
- Python 3.12
- Django 5.2.x
- Django REST Framework
- SQLite

### AI
- Local pretrained/off-the-shelf computer-vision model
- CPU inference only
- Hosted vision-language model for title/author extraction
- No model training or fine-tuning

### Deployment
- Not required
- The project must run locally from a clean clone by following the README

---

## Repository Structure

Target structure:

```text
shelfie/
├── AGENTS.md
├── README.md
├── AI_USAGE.md
├── catalog.csv
├── test_images/
│
├── frontend/
│   └── React Native + Expo app
│
└── backend/
    ├── .venv/                 # local only, never commit
    ├── manage.py
    ├── requirements.txt
    ├── config/
    │   ├── settings.py
    │   └── urls.py
    │
    └── library/
        ├── models.py
        ├── serializers.py
        ├── views.py
        ├── urls.py
        ├── services/
        │   ├── detection.py
        │   ├── vision.py
        │   └── matching.py
        └── tests/
```

Do not create extra infrastructure unless there is a clear assignment requirement.

---

## Core Engineering Principle

**Optimize for correctness, explainability, and scope control.**

Do not introduce:
- Docker unless it becomes necessary for reproducibility
- PostgreSQL
- Redis
- Celery
- Kubernetes
- microservices
- authentication
- cloud deployment
- elaborate state-management frameworks
- unnecessary abstractions

Every added dependency must solve a concrete problem.

The candidate must be able to explain and modify every important line of code during the presentation.

---

## Implementation Priorities

Work in this order unless there is a strong reason not to:

1. Backend and frontend scaffolding
2. Health endpoint
3. Image upload from Expo to Django
4. Local book/spine detection spike
5. Catalog creation
6. Matching logic + confidence scoring
7. Hosted VLM extraction
8. End-to-end analysis pipeline
9. Human-review flow
10. Library persistence
11. Failure handling
12. Tests
13. Latency/cost measurement
14. README + AI_USAGE.md
15. Demo rehearsal

Do not spend significant time polishing UI until the end-to-end flow works.

---

## Proposed Architecture

```text
Expo mobile app
      |
      | multipart/form-data
      v
Django REST API
      |
      v
Local CV detector (CPU)
      |
      | detected spine crops
      v
Hosted VLM
      |
      | title + author JSON
      v
Catalog matcher
      |
      | candidate + confidence
      v
Review / confirmation logic
      |
      v
SQLite
      |
      v
Expo results + library screens
```

Keep local detection, hosted vision extraction, catalog matching, and persistence as separate concerns.

---

## Backend API

Keep the API small.

### Health

```http
GET /api/health/
```

Response:

```json
{
  "status": "ok"
}
```

### Analyze Bookshelf

```http
POST /api/analyze/
Content-Type: multipart/form-data
```

Input:
- `image`

Response should include:
- detected books
- extracted title/author
- best catalog match
- confidence score
- review status
- errors/warnings where applicable

Example shape:

```json
{
  "books": [
    {
      "detection_id": "1",
      "extracted_title": "The Hobbit",
      "extracted_author": "J. R. R. Tolkien",
      "catalog_id": "42",
      "matched_title": "The Hobbit",
      "matched_author": "J.R.R. Tolkien",
      "confidence": 0.94,
      "requires_review": false
    }
  ],
  "warnings": []
}
```

### Library

```http
GET /api/library/
POST /api/library/
DELETE /api/library/<id>/
```

Do not add more endpoints unless needed.

---

## Computer Vision Rules

The local computer-vision model is responsible for **localization/detection**, not catalog identification.

Its job is to answer:

> Where are the individual book spines?

It should return bounding boxes or usable spine regions.

Requirements:
- pretrained/off-the-shelf weights only
- CPU inference
- no training
- no fine-tuning
- measure actual latency
- gracefully handle zero detections

Keep the detector behind a small service interface so it can be replaced without changing views or business logic.

Example conceptual interface:

```python
def detect_book_spines(image) -> list[Detection]:
    ...
```

---

## Hosted Vision-Language Model Rules

The hosted VLM is responsible for reading the detected spine image.

Its job is to answer:

> What title and author are visible on this spine?

Prefer structured JSON output.

Example:

```json
{
  "title": "The Hobbit",
  "author": "J.R.R. Tolkien",
  "readable": true
}
```

The backend must handle:
- API timeout
- provider error
- malformed JSON
- missing title
- missing author
- unreadable spine

Never assume the hosted model returns valid output.

Track:
- number of hosted calls
- approximate API cost per bookshelf image
- hosted-call latency

---

## Catalog Requirements

Ship a root-level:

```text
catalog.csv
```

It must contain at least **100 entries**.

Minimum fields:

```text
id
title
author
alternate_titles
```

Additional useful fields are allowed.

The catalog must deliberately contain ambiguity, including:
- multiple editions of the same work
- alternate publication titles
- genuinely different books sharing the same title
- omnibus/collected editions alongside individual books
- titles that are substrings of other titles
- author names written in multiple forms

Favor books people are realistically likely to own.

Do not make the catalog artificially clean.

---

## Matching Logic

Exact string matching is not sufficient.

Keep matching logic in a standalone service, preferably:

```text
backend/library/services/matching.py
```

At minimum consider:
- case normalization
- Unicode normalization
- punctuation normalization
- whitespace normalization
- author-name normalization
- alternate titles
- fuzzy title similarity
- fuzzy author similarity

The matcher should output:
- best candidate
- confidence score
- enough internal information to explain why it chose the candidate

A reasonable initial weighted score can be:

```text
combined_score =
    title_score * 0.70 +
    author_score * 0.30
```

The exact weights are not sacred. They must be explainable and tested.

Also consider the margin between the best and second-best candidates.

Example:

```text
best score:   0.91
second score: 0.90
```

This is highly ambiguous despite a high absolute score.

Whereas:

```text
best score:   0.87
second score: 0.48
```

may be much safer.

Do not silently accept ambiguous matches.

---

## Confidence / Human-in-the-Loop

The user must remain in control when the AI is uncertain.

Possible initial policy:

```text
confidence >= 0.85
    high confidence

0.60 <= confidence < 0.85
    review required

confidence < 0.60
    unmatched / review required
```

These thresholds can change after testing.

Low-confidence and unmatched books must never:
- disappear silently
- be accepted silently

The review screen is a product feature, not a debug screen.

Users should be able to:
- confirm
- correct
- select another candidate if supported
- discard

---

## Graceful Failure

No expected model or input failure should crash the app.

Explicitly handle:
- no image supplied
- invalid image
- zero books detected
- unreadable book spine
- local-model failure
- hosted-model timeout
- hosted-model HTTP error
- malformed hosted-model JSON
- no catalog match
- database failure where practical

Return meaningful API status codes and user-readable messages.

Avoid blank screens.

---

## Django Conventions

Use Django and DRF normally.

Keep:
- models in `models.py`
- API serializers in `serializers.py`
- request handling in `views.py`
- URL routing in `urls.py`
- AI/business logic in `services/`

Views should coordinate work, not contain the entire AI pipeline.

Bad:

```python
class AnalyzeView(...):
    # 300 lines containing image processing,
    # VLM calls, matching and persistence
```

Better:

```python
detections = detector.detect(image)
reads = vision_reader.read(detections)
matches = matcher.match(reads)
```

Avoid premature abstraction, but separate fundamentally different responsibilities.

---

## Frontend Conventions

Use React Native + Expo.

Keep the UI clean and functional.

Expected screens/flows:

```text
Home / Capture
      |
      v
Processing
      |
      v
Results
      |
      +--> Review uncertain books
      |
      v
Library
```

Prioritize:
- clear loading state
- clear error state
- confidence/review visibility
- obvious confirm/correct/discard actions

Do not spend assignment time on elaborate animations or branding.

---

## Testing

The assignment specifically values tests around matching logic.

Prioritize unit tests for:
- exact clean match
- punctuation differences
- capitalization differences
- alternate titles
- author initials
- `Lastname, Firstname`
- same-title ambiguity
- substring titles
- multiple editions
- low-confidence result
- close first/second candidate scores

A few meaningful tests are better than chasing coverage percentage.

Run backend tests with:

```bash
python manage.py test
```

---

## Performance and Cost

Before submission, measure rather than guess.

README must include actual measured values for:
- local detection latency
- hosted VLM latency
- total per-image latency
- estimated hosted API cost per image

Record the machine used for the benchmark.

Example:

```text
Machine: Intel MacBook Pro
Image: 3024 x 4032, 12 detected spines

Local detection: 1.8 s
Hosted VLM:      4.2 s
Matching:        0.04 s
Total:           6.1 s
Estimated cost:  $0.00xx / image
```

Do not write vague claims such as "fast" or "cheap" when numbers are available.

---

## Git Discipline

Use incremental, meaningful commits.

Examples:

```text
chore: scaffold Expo frontend and Django backend
feat: add backend health endpoint
feat: support bookshelf image upload
feat: add local book spine detection
feat: add catalog matching with confidence scores
test: cover ambiguous catalog matching
feat: integrate hosted vision model
feat: add review and library flow
docs: document architecture latency cost and AI usage
```

Do not submit one giant commit.

Once the repository link is formally submitted, **stop committing**.

Do not rewrite history near submission unless absolutely necessary.

---

## Environment and Secrets

Never commit:
- `.env`
- API keys
- `.venv`
- `node_modules`
- local SQLite database
- temporary model outputs
- uploaded runtime media unless intentionally used as test fixtures

Use environment variables for hosted-model credentials.

Provide `.env.example` when environment variables are required.

Example:

```text
VISION_API_KEY=
```

---

## README Requirements

Before submission, README should include:

1. Project overview
2. Architecture
3. Setup from a clean clone
4. Backend run instructions
5. Frontend run instructions
6. Required environment variables
7. Catalog design and deliberate ambiguity
8. Matching strategy
9. Confidence/review strategy
10. Local vs hosted AI routing rationale
11. Measured latency
12. Estimated API cost
13. Failure-handling approach
14. Tests
15. Tradeoffs
16. What was intentionally cut
17. What would be done with another day

All commands in the README must be tested from the repository structure actually submitted.

---

## AI_USAGE.md

Be explicit and truthful about AI assistance.

Document:
- tools used
- where they were used
- what kinds of code/content they helped produce
- that generated code was reviewed and understood

Do not pretend AI was not used.

---

## Definition of Done

The assignment is done when a reviewer can:

1. Clone the repo.
2. Follow the README.
3. Start Django.
4. Start Expo.
5. Submit a real bookshelf photo.
6. See detected/read books.
7. See catalog matches and confidence.
8. Review uncertain results.
9. Confirm books into the library.
10. View persisted library books.
11. Encounter common failures without crashes.
12. Run meaningful matcher tests.
13. See real latency and cost numbers in README.
14. Inspect a clear AI usage disclosure.
15. Ask the candidate to explain or modify the code without the architecture collapsing.

A smaller implementation that satisfies these conditions is better than a larger unfinished implementation.

---

## Run Reporting and Persistent Project Progress

Every meaningful Codex run must leave behind a clear written record.

A **meaningful run** is any run that does one or more of the following:

- creates or modifies project files
- installs or removes dependencies
- changes configuration
- runs tests or verification
- makes an architecture or implementation decision
- discovers a blocker, compatibility issue, or failure
- completes or advances a milestone

Do not rely only on terminal output or chat history. Persist the project state in `codex_docs/`.

### Required Reporting Files

Maintain both of these files:

```text
codex_docs/
├── last_run.md
└── progress_report.md
```

If either file does not exist, create it.

### `codex_docs/last_run.md`

This file represents **only the most recent run**.

Overwrite it at the end of every meaningful run.

Use this structure:

```markdown
# Last Run

## Run
- Date/time:
- Task:
- Result: Completed / Partial / Blocked / Failed

## Summary
A short factual description of what happened during this run.

## Work Completed
- ...

## Files Changed
- `path/to/file` — what changed and why

## Dependencies / Environment Changes
- ...

## Commands / Verification
- `command` — result

## Decisions Made
- decision
- reason
- tradeoff

## Problems / Blockers
- problem
- current impact
- attempted resolution

## What Remains
- ...

## Recommended Next Step
The single most useful next action.
```

Be factual. Do not say something works unless it was actually executed or verified.

### `codex_docs/progress_report.md`

This is the **cumulative project record**.

It has two responsibilities:

1. Show the current state of the entire assignment.
2. Preserve an append-only history of meaningful runs.

The file should contain:

```markdown
# Shelfie Progress Report

## Current Snapshot
- Overall status:
- Approximate completion:
- Current milestone:
- Current blocker:
- Critical next step:

## Milestones

| Milestone | Weight | Status | Progress | Evidence / Notes |
|---|---:|---|---:|---|
| 1. Project setup | 10% | ... | ... | ... |
| 2. Image upload/API flow | 10% | ... | ... | ... |
| 3. Local spine detection | 20% | ... | ... | ... |
| 4. Catalog + matching | 20% | ... | ... | ... |
| 5. Hosted VLM integration | 15% | ... | ... | ... |
| 6. Review + persistence | 10% | ... | ... | ... |
| 7. Failure handling + tests | 10% | ... | ... | ... |
| 8. README, metrics + demo readiness | 5% | ... | ... | ... |

## Critical Path
1. ...
2. ...
3. ...

## Known Risks
- ...

## Run History

### Run YYYY-MM-DD HH:MM — <short task name>
**Result:** Completed / Partial / Blocked / Failed

**Progress made**
- ...

**Milestone movement**
- ...

**Verification**
- ...

**Blockers / risks**
- ...

**Next**
- ...
```

### Progress Rules

At the end of every meaningful run:

1. Update the **Current Snapshot**.
2. Update milestone status/progress based on actual evidence.
3. Update the **Critical Path** if priorities changed.
4. Update **Known Risks** if new risks appeared or old ones were resolved.
5. **Append** a new entry to the bottom of `Run History`.
6. Never delete or rewrite older Run History entries except to correct an obvious factual error.
7. Rewrite `last_run.md` so it contains only the newest run.

### Milestone Status Values

Use only:

```text
Not started
In progress
Blocked
Done
```

### Progress Estimation

Progress percentages are estimates, not marketing.

Do not increase progress merely because code was written.

Count progress only when there is evidence such as:

- code exists and is understood
- required command succeeds
- feature works locally
- test passes
- failure path has been exercised
- latency/cost has been measured
- README instructions have been verified

If a feature exists but is broken or unverified, report it as partial.

The weighted milestone table should be used to estimate overall completion. Avoid fake precision. Prefer values such as:

```text
~20%
~45%
~70%
```

rather than unsupported values such as:

```text
63.7%
```

### Reporting Failures

Do not hide failed attempts.

If a run fails:

- record what failed
- record the exact error or concise error summary
- record what was tried
- record whether files were left partially modified
- identify the safest next action

A failed experiment that rules out a bad technical approach is still useful progress, but it must not be reported as a completed feature.

### Git Awareness

Each run report should note:

- current branch
- whether the working tree is clean or dirty
- whether a commit was created
- commit hash/message if a commit was created

Do not create a commit merely to make the report look complete.

### End-of-Run Terminal Report

In addition to writing the reporting files, finish each Codex run with a concise terminal summary containing:

- result
- what changed
- verification performed
- current overall progress
- current milestone
- blockers
- next recommended action
- paths to `codex_docs/last_run.md` and `codex_docs/progress_report.md`

The persisted Markdown files are the source of truth; the terminal summary is only a convenience.

