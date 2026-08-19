# Shelfie Architecture

Shelfie is a small Django/Expo application whose modules follow product
responsibilities. Framework edges coordinate the flow; model, matching, policy, and
persistence details stay behind focused service boundaries.

## End-to-end flow

```text
Expo photo picker
→ POST /api/analyze/ (multipart image)
→ Pillow validation and EXIF orientation correction
→ CPU DETR book-region detection
→ padded in-memory crops and review thumbnails
→ bounded concurrent Qwen/OpenRouter crop reading
→ Unicode-aware catalog ranking
→ conservative review policy
→ spatial duplicate consolidation
→ ordinary/series presentation grouping
→ explicit user add, correction, or discard
→ GET/POST/DELETE /api/library/ backed by SQLite
```

The analysis response is additive: raw detections and reads remain available alongside
the smaller consolidated review items and presentation groups. Grouping therefore
reduces review work without becoming a new source of identification truth.

## Backend boundaries

- `library/api/` translates HTTP requests and known service errors; it does not own AI
  or matching behavior.
- `services/image_validation.py` fully decodes uploads and produces upright RGB pixels.
- `services/spine_detection.py` owns the cached CPU-only DETR checkpoint, threshold,
  timing, and safe book-region boxes.
- `services/crop_processing.py` creates bounded padded crops and compact source
  thumbnails in memory.
- `services/book_reading.py` owns Qwen/OpenRouter requests, strict response validation,
  bounded concurrency, cost/latency accounting, and per-crop failure isolation.
- `services/catalog_matching.py` loads the CSV and returns normalized fuzzy title and
  author evidence, including a runner-up and margin.
- `services/review_policy.py` alone maps reader/matcher evidence to high confidence,
  review required, or unmatched. It also decides whether a catalog suggestion is safe
  enough to show.
- `services/result_consolidation.py` conservatively joins spatial duplicates while
  preserving source indices and raw results.
- `services/review_grouping.py` derives display-only ordinary and series groups from
  consolidated items.
- `services/analysis_pipeline.py` orchestrates those services and preserves partial
  successes and warnings.
- `models.py` and the library serializer/API persist only confirmed catalog or manual
  book fields in SQLite.

Ordinary dataclass contracts in `library/contracts/analysis.py` keep model/provider
objects from leaking across these boundaries.

## Frontend boundaries

- `App.tsx` remains the thin Expo entry point.
- `src/screens/ScanScreen.tsx` coordinates selection, analysis, review, and library
  state.
- `src/api/shelfieApi.ts` owns the base URL, multipart/JSON requests, response
  validation, and user-facing network errors.
- `src/components/` owns photo selection, analysis presentation, book review actions,
  and the persisted library list.
- `src/types/api.ts` mirrors the public API contracts.

Every result, including a high-confidence one, needs an explicit user action before a
library write. Uncertain, unreadable, failed, and likely non-book regions stay visible
for manual correction or discard.

## Replaceability and failure isolation

The detector returns ordinary boxes; the reader returns validated book-read contracts;
the matcher returns ranking evidence; and the review policy returns product decisions.
This keeps likely changes localized—for example, replacing DETR does not require a new
matcher, and changing review thresholds does not alter hosted requests or persistence.

Expected remote failures become per-crop results so other crops survive. Invalid
images, unavailable local services, and missing hosted configuration are translated at
the API boundary. No model output is treated as confirmed library data without the
human step.
