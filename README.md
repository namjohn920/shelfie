# Shelfie

Shelfie turns a bookshelf photo into a reviewable personal library. An Expo app uploads
the photo to Django; a local CPU detector finds book regions, a hosted vision-language
model reads them, and explainable catalog matching plus explicit human confirmation
decide what is saved to SQLite.

## Architecture

```text
Expo photo
→ Django REST API
→ image validation and EXIF orientation correction
→ local CPU DETR book detection
→ padded in-memory crops
→ hosted Qwen VLM through OpenRouter
→ normalized catalog matching
→ confidence and review policy
→ duplicate consolidation
→ presentation grouping
→ human confirmation or correction
→ SQLite library
```

The pipeline is split into focused services for validation, detection, cropping, hosted
reading, matching, review policy, consolidation, grouping, and persistence. These
modules exchange small data contracts, so a detector, hosted reader, matching rule, or
review threshold can be replaced without rewriting the API or mobile flow. See
[`codex_docs/architecture_plan.md`](codex_docs/architecture_plan.md) for the boundary
map.

## Run locally

Prerequisites:

- Python 3.12.14
- Node.js 22.23.1 through `nvm`
- an OpenRouter API key
- a phone with Expo Go or a supported simulator
- internet access for the first DETR checkpoint download and hosted reading

### Backend

From the repository root:

```bash
cd backend
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp ../.env.example .env
```

The version check should report `Python 3.12.14`. Edit `backend/.env` and use a
placeholder-shaped value only in shared documentation:

```dotenv
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
```

Never commit the real value. Initialize SQLite and start Django on the LAN:

```bash
python manage.py migrate
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

The first analysis may take longer while Transformers downloads and loads
`facebook/detr-resnet-50` revision `no_timm`.

### Frontend

In a second terminal, from the repository root:

```bash
cd frontend
source "$HOME/.nvm/nvm.sh"
nvm install
nvm use
npm ci
cp .env.example .env
```

Set the API base URL to the computer's LAN address. `192.168.1.50` is only a generic
example; use the address reachable from the phone:

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000
```

The implemented variable is `EXPO_PUBLIC_API_BASE_URL`; `EXPO_PUBLIC_API_URL` is not
read by the app. Keep the phone and computer on the same network, then start Expo:

```bash
npx expo start
```

Open the QR code in Expo Go, choose a bookshelf photo, and tap **Analyze Shelf**.

### Quick start after setup

Once dependencies, environment files, and migrations are already configured, start the
app in two terminals.

Terminal 1 — Django backend:

```bash
cd backend
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Terminal 2 — Expo frontend:

```bash
cd frontend
source "$HOME/.nvm/nvm.sh"
nvm use
npx expo start --clear
```

Scan the QR code with Expo Go. If Expo reports that port `8081` is already in use, allow
it to use another available port such as `8082` rather than terminating an unrelated
process.

## Catalog and matching

[`catalog.csv`](catalog.csv) contains 151 UTF-8 entries and is deliberately not a clean
one-title-per-work dataset. It includes alternate publication titles, separate
editions, genuinely different books with the same title, omnibus and contained
volumes, substring titles, author-name variants, and Unicode/non-English titles.

The matcher applies Unicode, case, punctuation, whitespace, and author-order
normalization, then fuzzy-scores title and author evidence. It returns the best
candidate, runner-up, component scores, combined score, and best-versus-runner-up
margin. A candidate floor controls ranking output; the separate conservative review
policy decides whether that evidence is strong enough to show or label high confidence.

## AI/CV decisions

Local DETR handles spatial localization while hosted Qwen handles semantic reading.
Keeping detection local satisfies the CPU/off-the-shelf CV constraint and avoids
sending the entire shelf for localization. Hosted reading is reserved for the smaller
crops because multilingual, rotated spine text is better suited to a VLM than the
local detector. Each crop call remains independently traceable and independently
fallible.

DETR was selected after comparing local CPU alternatives. OWLv2 produced useful,
tighter-looking spine regions but had materially higher CPU latency; YOLOv4-tiny was
faster but had visibly weaker coverage on the inspected shelves. DETR offered the most
usable coverage/latency tradeoff for this product path. The photos had no labeled
ground truth, so these observations are not accuracy measurements.

The hosted reader was selected with a small comparison on 12 real DETR crops:

| Model | Valid responses | Median latency | Total cost |
|---|---:|---:|---:|
| Qwen3-VL 8B | 12/12 | 1.4680 s | $0.00160195 |
| GPT-4.1-mini | 12/12 | 2.4268 s | $0.00561000 |
| Gemini 2.5 Flash | 11/12 | 3.1705 s | $0.01133860 |

This was a small real-crop comparison of structured-response reliability, latency,
cost, and visible evidence—not an accuracy benchmark. It supported selecting
`qwen/qwen3-vl-8b-instruct` as the first hosted reader.

## Human-in-the-loop behavior

No analysis result is saved automatically. A high-confidence match still requires an
explicit **Add to Library** action. Partial, uncertain, unmatched, failed, and likely
non-book regions remain reviewable: the user can accept a sufficiently supported
catalog suggestion, enter a manual title/author, or discard the item.

The response preserves detection IDs, source crops, raw reads, catalog scoring, the
runner-up, margin, and review reasons. Duplicate consolidation and conservative
ordinary/series grouping reduce repeated actions without deleting the underlying raw
evidence. Only user-confirmed canonical catalog data or manual corrections persist to
SQLite.

## Failure handling

- Missing or invalid image uploads return clear `400` responses.
- Zero detections return a valid empty analysis and make no hosted calls.
- Detector or catalog initialization failures return a concise `503` response.
- A missing `OPENROUTER_API_KEY` returns `503` only when detected crops need reading.
- Hosted timeouts, HTTP/provider failures, malformed JSON, and invalid schemas are
  isolated to the individual crop; successful crops remain available.
- Unreadable, uncertain, and likely non-book regions remain visible for discard or
  manual correction.
- Weak or ambiguous catalog matches are kept out of the high-confidence path; weak
  candidates may also be hidden from the suggested-match UI while raw evidence remains
  traceable.

## Measured production-path evidence

The following is one representative shelf/run on the Intel x86_64 macOS development
machine. It measures the real production path and is neither an accuracy result nor a
latency guarantee.

| Measurement | Result |
|---|---:|
| Source / EXIF-upright image | 4032×3024 / 3024×4032 |
| DETR detections | 58 |
| Detector total | 14.3639 s |
| Model load within detector total | 10.0508 s |
| Detector inference | 3.8209 s |
| Hosted crop results | 58/58 successful |
| Hosted wall time | 20.5433 s |
| Analysis wall time | 37.2287 s |
| Raw book reads | 86 |
| Consolidated review items | 62 |
| Presentation groups | 40 |
| Hosted cost | $0.01011149 |

With eight hosted workers and OpenRouter latency-first eligible-provider routing, this
run measured 37.2287 s versus 65.5551 s for the latest comparable four-worker/default-
routing run. The observed reduction was 28.3264 s (43.2%), but one run cannot isolate
concurrency from provider, route, network, or model variance and does not establish a
stable speedup.

## Verification

Verification status:

- Django system check: passed
- migration consistency check: passed, no changes detected
- backend suite: 123 tests passed
- TypeScript: passed
- Expo Doctor: previously passed 18/18; in the final restricted-network cleanup pass,
  16/18 checks completed and the two Expo metadata checks could not reach their remote
  services

Run the same checks with:

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py makemigrations --check
python manage.py test

cd ../frontend
source "$HOME/.nvm/nvm.sh"
nvm use
npx tsc --noEmit
npx expo-doctor
```

The normal automated suite uses fakes/mocks and does not initialize DETR or make
OpenRouter calls.

## Tradeoffs and limitations

- OCR/VLM output is probabilistic; rotated, partially visible, reflective, or distant
  spines remain difficult.
- DETR can return overlapping or multi-book regions.
- Conservative exact presentation grouping can under-group noisy OCR variants.
- Provider and network latency, availability, and per-image cost vary.
- The one-shelf measurements above are product-path observations, not accuracy metrics.
- Review thresholds are deliberately conservative starting points, not calibrated
  production truth.
- Authentication, multi-user ownership, deployment, and production hardening are out
  of scope.
- CPU model dependencies and the downloaded checkpoint are large.

## What I would do next with another day

1. Build a labeled multi-shelf evaluation set and measure detection, reading, matching,
   consolidation, and grouping separately.
2. Calibrate matching/review thresholds from confirmed outcomes, then test broader
   difficult-photo cases and rotated/partially visible spines.
3. Evaluate targeted detector/crop refinements only for labeled failure patterns.
4. Show richer runner-up evidence and correction choices in the review UI.
5. Add production observability, then consider caching or crop batching only where
   measurements show a worthwhile latency/cost benefit.

These are follow-up priorities, not implemented features.
