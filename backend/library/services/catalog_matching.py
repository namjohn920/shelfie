from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Literal

from rapidfuzz import fuzz

from library.contracts.analysis import (
    BookRead,
    CatalogEntry,
    MatchCandidate,
    MatchResult,
)
from library.services.text_normalization import normalize_author, normalize_text


TITLE_WEIGHT = 0.70
AUTHOR_WEIGHT = 0.30
CANDIDATE_FLOOR = 60.0
CONTAINED_TITLE_SCORE_CAP = 92.0
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[3] / 'catalog.csv'
REQUIRED_CATALOG_COLUMNS = {
    'catalog_id',
    'title',
    'author',
    'alternate_titles',
    'author_aliases',
    'edition',
    'contains_titles',
    'ambiguity_tags',
}


class CatalogError(ValueError):
    """Raised when the catalog cannot satisfy its readable CSV contract."""


def _split_list(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or '').split('|') if part.strip())


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> tuple[CatalogEntry, ...]:
    with path.open(encoding='utf-8', newline='') as catalog_file:
        reader = csv.DictReader(catalog_file)
        columns = set(reader.fieldnames or ())
        missing_columns = REQUIRED_CATALOG_COLUMNS - columns
        if missing_columns:
            raise CatalogError(
                f'Catalog is missing required columns: {", ".join(sorted(missing_columns))}'
            )

        rows = tuple(reader)
        if any(None in row for row in rows):
            raise CatalogError('Catalog row has more values than the header allows.')
        entries = tuple(
            CatalogEntry(
                catalog_id=(row['catalog_id'] or '').strip(),
                title=(row['title'] or '').strip(),
                author=(row['author'] or '').strip(),
                alternate_titles=_split_list(row['alternate_titles']),
                author_aliases=_split_list(row['author_aliases']),
                edition=(row['edition'] or '').strip(),
                contains_titles=_split_list(row['contains_titles']),
                ambiguity_tags=_split_list(row['ambiguity_tags']),
            )
            for row in rows
        )

    seen_ids: set[str] = set()
    for entry in entries:
        if not entry.catalog_id or not entry.title or not entry.author:
            raise CatalogError('Every catalog row needs an ID, title, and author.')
        if entry.catalog_id in seen_ids:
            raise CatalogError(f'Duplicate catalog ID: {entry.catalog_id}')
        seen_ids.add(entry.catalog_id)
    return entries


def _title_variants(
    entry: CatalogEntry,
) -> Iterable[tuple[str, Literal['canonical', 'alternate', 'contained'], float]]:
    yield entry.title, 'canonical', 100.0
    for title in entry.alternate_titles:
        yield title, 'alternate', 100.0
    for title in entry.contains_titles:
        yield title, 'contained', CONTAINED_TITLE_SCORE_CAP


def _title_match(
    query: str,
    entry: CatalogEntry,
) -> tuple[float, str, Literal['canonical', 'alternate', 'contained']]:
    best_score = -1.0
    best_title = entry.title
    best_evidence: Literal['canonical', 'alternate', 'contained'] = 'canonical'
    for title, evidence, score_cap in _title_variants(entry):
        score = min(float(fuzz.WRatio(query, normalize_text(title))), score_cap)
        if score > best_score:
            best_score = score
            best_title = title
            best_evidence = evidence
    return best_score, best_title, best_evidence


def _author_match(query: str, entry: CatalogEntry) -> tuple[float, str]:
    best_score = -1.0
    best_author = entry.author
    for author in (entry.author, *entry.author_aliases):
        normalized = normalize_author(author)
        score = max(
            float(fuzz.WRatio(query, normalized)),
            float(fuzz.token_sort_ratio(query, normalized)),
            float(fuzz.token_set_ratio(query, normalized)),
        )
        if score > best_score:
            best_score = score
            best_author = author
    return best_score, best_author


def match_catalog(
    book_read: BookRead,
    catalog: Iterable[CatalogEntry] | None = None,
    *,
    title_weight: float = TITLE_WEIGHT,
    author_weight: float = AUTHOR_WEIGHT,
    candidate_floor: float = CANDIDATE_FLOOR,
) -> MatchResult:
    if title_weight < 0.0 or author_weight < 0.0:
        raise ValueError('Matcher weights cannot be negative.')
    if abs(title_weight + author_weight - 1.0) > 1e-9:
        raise ValueError('Matcher weights must add up to 1.0.')

    normalized_title = normalize_text(book_read.title)
    normalized_author = normalize_author(book_read.author)
    if not normalized_title or book_read.readability == 'unreadable':
        return MatchResult(None, None, None, None, None, None, None, candidate_floor)

    candidates: list[MatchCandidate] = []
    for entry in catalog if catalog is not None else load_catalog():
        title_score, matched_title, title_evidence = _title_match(
            normalized_title,
            entry,
        )
        author_score: float | None = None
        matched_author: str | None = None
        if normalized_author:
            author_score, matched_author = _author_match(normalized_author, entry)
            combined_score = (
                title_score * title_weight + author_score * author_weight
            )
        else:
            combined_score = title_score
        candidates.append(
            MatchCandidate(
                entry=entry,
                matched_title=matched_title,
                matched_author=matched_author,
                title_evidence=title_evidence,
                title_score=round(title_score, 4),
                author_score=(
                    round(author_score, 4) if author_score is not None else None
                ),
                combined_score=round(combined_score, 4),
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.combined_score,
            -candidate.title_score,
            -(candidate.author_score if candidate.author_score is not None else -1.0),
            candidate.entry.catalog_id,
        )
    )
    if not candidates or candidates[0].combined_score < candidate_floor:
        return MatchResult(None, None, None, None, None, None, None, candidate_floor)

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    second_score = second.combined_score if second else None
    margin = best.combined_score - second_score if second_score is not None else None
    return MatchResult(
        best_candidate=best,
        second_candidate=second,
        title_score=best.title_score,
        author_score=best.author_score,
        combined_score=best.combined_score,
        second_score=second_score,
        margin=round(margin, 4) if margin is not None else None,
        candidate_floor=candidate_floor,
    )
