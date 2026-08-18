# Shelfie Architecture Plan

## Purpose and Current Scope

Shelfie uses small, descriptive modules with one primary responsibility. This plan
records how the working Milestone 2 upload flow is separated now and where later
computer-vision blocks belong. It does not implement the detector, hosted reader,
catalog matcher, review flow, or persistence.

Future service files are created only when they contain real implementation. They are
listed here instead of being added as empty placeholders.

## Current Working Flow

```text
Expo ScanScreen
→ shelfieApi multipart request
→ Django analyze endpoint
→ image_validation Pillow decode
→ factual upload metadata
→ ScanScreen success or error state
```

### Backend responsibilities

- `library/api/health.py` owns only `GET /api/health/`.
- `library/api/analyze.py` owns multipart request handling, known validation-error
  translation, and response serialization for `POST /api/analyze/`.
- `library/services/image_validation.py` owns Pillow decoding, the invalid-image
  failure, and factual filename, content type, width, and height extraction.
- `library/urls.py` maps stable endpoint paths to their handlers.

### Frontend responsibilities

- `App.tsx` is the Expo entry point and renders the current screen.
- `src/screens/ScanScreen.tsx` owns selected-photo, loading, result, and error state
  and coordinates the user flow.
- `src/components/BookshelfPhotoPicker.tsx` owns permission/selection interaction
  and the selected-photo preview. It performs no backend networking.
- `src/components/UploadResultCard.tsx` renders successful upload metadata.
- `src/api/shelfieApi.ts` owns API URL normalization, `FormData`, the analyze request,
  response validation, and user-facing network/API error translation.
- `src/types/api.ts` owns only the API result type used by the current UI.

## Future Analysis Pipeline

The intended pipeline order is:

```text
image validation
→ spine detection
→ crop processing
→ book reading
→ catalog matching
→ review policy
```

`services/analysis_pipeline.py` will coordinate those blocks and collect results, but
will not absorb their model-, provider-, matching-, or policy-specific behavior.

The future service responsibilities are:

- `services/spine_detection.py`: run the selected pretrained local CPU detector and
  return spine regions. It localizes books; it does not read titles or choose catalog
  entries.
- `services/crop_processing.py`: turn detected regions into usable crops and own any
  justified orientation, expansion, resize, or contrast preparation. Fallback work is
  bounded rather than open-ended.
- `services/book_reading.py`: ask the hosted visual reader for evidence visible on a
  crop and validate its response. It preserves Unicode and represents missing or
  uncertain text explicitly; it does not perform catalog matching.
- `services/catalog_matching.py`: rank catalog candidates from a book read and return
  the best candidate, an optional runner-up, and explainable score/confidence evidence.
  It may return no match when evidence is insufficient.
- `services/review_policy.py`: decide whether a result can be accepted, needs review,
  is unmatched, or is unreadable. Exact policy and thresholds wait for matching tests
  and real evidence.
- `services/analysis_pipeline.py`: orchestrate the blocks per detected spine, isolate
  per-spine failures, and preserve successful partial results plus warnings for the
  overall bookshelf.

## Future Data Concepts

Exact fields will be finalized when the relevant implementation is built. The small
contracts must support:

- `SpineDetection`: a stable detection identity, its image region, and useful detector
  evidence.
- `BookRead`: optional title, optional author, optional raw text, optional language,
  and `readability` of `readable`, `partial`, or `unreadable`.
- `MatchResult`: the best candidate, possibly the second candidate, and the scoring or
  confidence evidence needed to explain ambiguity. The best candidate may be absent.
- `ReviewDecision`: an explicit downstream decision that preserves uncertainty rather
  than fabricating a confident identification.

## Difficult-Photo Behavior

Mixed-language and non-Latin text, horizontal or rotated books, partial occlusion,
backwards books, glare, dark spines, small or distant books, and missing catalog entries
are normal outcomes to design for.

The operating principle is:

```text
support what can be read
→ preserve uncertainty
→ one bounded fallback where justified
→ review, unmatched, or unreadable
→ never fabricate a confident book
```

One failed or unreadable spine must not crash or erase the rest of the bookshelf
analysis. The concrete detector, preprocessing strategy, reader provider, matching
evidence, retry rule, and review thresholds remain implementation decisions for later
milestones.
