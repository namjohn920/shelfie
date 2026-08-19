from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def clipped(self, image_width: int, image_height: int) -> BoundingBox:
        return BoundingBox(
            left=min(max(self.left, 0.0), float(image_width)),
            top=min(max(self.top, 0.0), float(image_height)),
            right=min(max(self.right, 0.0), float(image_width)),
            bottom=min(max(self.bottom, 0.0), float(image_height)),
        )

    def as_dict(self) -> dict[str, float]:
        return {
            'left': round(self.left, 2),
            'top': round(self.top, 2),
            'right': round(self.right, 2),
            'bottom': round(self.bottom, 2),
        }


@dataclass(frozen=True)
class SpineDetection:
    detection_index: int
    box: BoundingBox
    confidence: float
    label: str = 'book'

    def as_dict(self) -> dict[str, object]:
        return {
            'detection_index': self.detection_index,
            'label': self.label,
            'confidence': round(self.confidence, 6),
            'box': self.box.as_dict(),
        }


@dataclass(frozen=True)
class DetectorTiming:
    model_load_seconds: float
    preprocess_seconds: float
    inference_seconds: float
    postprocess_seconds: float
    total_seconds: float
    model_was_cached: bool

    def as_dict(self) -> dict[str, float | bool]:
        return {
            'model_load_seconds': round(self.model_load_seconds, 4),
            'preprocess_seconds': round(self.preprocess_seconds, 4),
            'inference_seconds': round(self.inference_seconds, 4),
            'postprocess_seconds': round(self.postprocess_seconds, 4),
            'total_seconds': round(self.total_seconds, 4),
            'model_was_cached': self.model_was_cached,
        }


@dataclass(frozen=True)
class DetectionResult:
    detections: tuple[SpineDetection, ...]
    checkpoint: str
    threshold: float
    image_width: int
    image_height: int
    timing: DetectorTiming


Readability = Literal['readable', 'partial', 'unreadable']
CropType = Literal['single_book', 'multiple_books', 'unreadable']
RegionType = Literal['book', 'multiple_books', 'non_book', 'uncertain']
ReaderStatus = Literal['ok', 'error']
ReviewStatus = Literal['high_confidence', 'review_required', 'unmatched']


@dataclass(frozen=True)
class BookRead:
    title: str | None
    author: str | None = None
    volume: str | None = None
    raw_text: str | None = None
    language: str | None = None
    readability: Readability = 'readable'

    def as_dict(self) -> dict[str, str | None]:
        return {
            'title': self.title,
            'author': self.author,
            'volume': self.volume,
            'raw_text': self.raw_text,
            'language': self.language,
            'readability': self.readability,
        }


@dataclass(frozen=True)
class CropReadResult:
    detection_index: int
    crop_type: CropType | None
    region_type: RegionType | None
    region_text: str | None
    readability: Readability | None
    books: tuple[BookRead, ...]
    status: ReaderStatus
    error_code: str | None
    error_message: str | None
    latency_seconds: float
    cost_usd: float | None
    model_id: str
    provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    notes: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            'detection_index': self.detection_index,
            'crop_type': self.crop_type,
            'region_type': self.region_type,
            'region_text': self.region_text,
            'readability': self.readability,
            'book_count': len(self.books),
            'status': self.status,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'latency_seconds': round(self.latency_seconds, 4),
            'cost_usd': self.cost_usd,
            'model': self.model_id,
            'provider': self.provider,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'notes': self.notes,
        }


@dataclass(frozen=True)
class ReaderBatchResult:
    results: tuple[CropReadResult, ...]
    model_id: str
    attempted_crops: int
    successful_crops: int
    failed_crops: int
    wall_seconds: float
    total_cost_usd: float

    def as_dict(self) -> dict[str, object]:
        return {
            'model': self.model_id,
            'attempted_crops': self.attempted_crops,
            'successful_crops': self.successful_crops,
            'failed_crops': self.failed_crops,
            'wall_seconds': round(self.wall_seconds, 4),
            'total_cost_usd': round(self.total_cost_usd, 8),
            'crop_results': [result.as_dict() for result in self.results],
        }


@dataclass(frozen=True)
class CatalogEntry:
    catalog_id: str
    title: str
    author: str
    alternate_titles: tuple[str, ...] = ()
    author_aliases: tuple[str, ...] = ()
    edition: str = ''
    contains_titles: tuple[str, ...] = ()
    ambiguity_tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str]:
        return {
            'catalog_id': self.catalog_id,
            'title': self.title,
            'author': self.author,
            'edition': self.edition,
        }


@dataclass(frozen=True)
class MatchCandidate:
    entry: CatalogEntry
    matched_title: str
    matched_author: str | None
    title_evidence: Literal['canonical', 'alternate', 'contained']
    title_score: float
    author_score: float | None
    combined_score: float

    def as_dict(self) -> dict[str, object]:
        return {
            'catalog': self.entry.as_dict(),
            'matched_title': self.matched_title,
            'matched_author': self.matched_author,
            'title_evidence': self.title_evidence,
            'title_score': self.title_score,
            'author_score': self.author_score,
            'combined_score': self.combined_score,
        }


@dataclass(frozen=True)
class MatchResult:
    best_candidate: MatchCandidate | None
    second_candidate: MatchCandidate | None
    title_score: float | None
    author_score: float | None
    combined_score: float | None
    second_score: float | None
    margin: float | None
    candidate_floor: float

    def as_dict(self) -> dict[str, object]:
        return {
            'best_candidate': (
                self.best_candidate.as_dict() if self.best_candidate else None
            ),
            'second_candidate': (
                self.second_candidate.as_dict() if self.second_candidate else None
            ),
            'title_score': self.title_score,
            'author_score': self.author_score,
            'combined_score': self.combined_score,
            'second_score': self.second_score,
            'margin': self.margin,
            'candidate_floor': self.candidate_floor,
        }


@dataclass(frozen=True)
class ReviewDecision:
    status: ReviewStatus
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'status': self.status,
            'reasons': list(self.reasons),
        }


@dataclass(frozen=True)
class AnalyzedBook:
    detection_index: int
    book_index: int
    read: BookRead | None
    match: MatchResult | None
    review: ReviewDecision
    suggested_match: MatchCandidate | None = None
    crop_type: CropType | None = None
    region_type: RegionType | None = None
    region_text: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            'detection_index': self.detection_index,
            'book_index': self.book_index,
            'read': self.read.as_dict() if self.read else None,
            'match': self.match.as_dict() if self.match else None,
            'suggested_match': (
                self.suggested_match.as_dict() if self.suggested_match else None
            ),
            'crop_type': self.crop_type,
            'region_type': self.region_type,
            'region_text': self.region_text,
            'review': self.review.as_dict(),
        }


@dataclass(frozen=True)
class ReviewItem:
    item_id: str
    representative: AnalyzedBook
    source_detection_indices: tuple[int, ...]
    duplicate_count: int

    def as_dict(self) -> dict[str, object]:
        serialized = self.representative.as_dict()
        serialized.update(
            {
                'id': self.item_id,
                'source_detection_indices': list(self.source_detection_indices),
                'duplicate_count': self.duplicate_count,
            }
        )
        return serialized


@dataclass(frozen=True)
class ReviewVolumeBucket:
    bucket_id: str
    volume: str
    representative_item_id: str
    items: tuple[ReviewItem, ...]
    source_detection_indices: tuple[int, ...]
    item_count: int
    total_entries: int
    detection_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            'id': self.bucket_id,
            'volume': self.volume,
            'representative_item_id': self.representative_item_id,
            'items': [item.as_dict() for item in self.items],
            'source_detection_indices': list(self.source_detection_indices),
            'item_count': self.item_count,
            'total_entries': self.total_entries,
            'detection_count': self.detection_count,
        }


@dataclass(frozen=True)
class OrdinaryReviewGroup:
    group_id: str
    title: str | None
    author: str | None
    review_status: ReviewStatus
    representative_item_id: str
    items: tuple[ReviewItem, ...]
    source_detection_indices: tuple[int, ...]
    item_count: int
    total_entries: int
    detection_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            'id': self.group_id,
            'group_type': 'ordinary',
            'title': self.title,
            'author': self.author,
            'review_status': self.review_status,
            'representative_item_id': self.representative_item_id,
            'items': [item.as_dict() for item in self.items],
            'source_detection_indices': list(self.source_detection_indices),
            'item_count': self.item_count,
            'total_entries': self.total_entries,
            'detection_count': self.detection_count,
        }


@dataclass(frozen=True)
class SeriesReviewGroup:
    group_id: str
    title: str | None
    author: str | None
    review_status: ReviewStatus
    representative_item_id: str
    volumes: tuple[ReviewVolumeBucket, ...]
    unknown_volume_items: tuple[ReviewItem, ...]
    source_detection_indices: tuple[int, ...]
    item_count: int
    total_entries: int
    detection_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            'id': self.group_id,
            'group_type': 'series',
            'title': self.title,
            'author': self.author,
            'review_status': self.review_status,
            'representative_item_id': self.representative_item_id,
            'volumes': [volume.as_dict() for volume in self.volumes],
            'unknown_volume_items': [
                item.as_dict() for item in self.unknown_volume_items
            ],
            'source_detection_indices': list(self.source_detection_indices),
            'item_count': self.item_count,
            'total_entries': self.total_entries,
            'detection_count': self.detection_count,
        }


ReviewGroup = OrdinaryReviewGroup | SeriesReviewGroup


@dataclass(frozen=True)
class CropThumbnail:
    detection_index: int
    data_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            'detection_index': self.detection_index,
            'data_url': self.data_url,
        }


@dataclass(frozen=True)
class AnalysisPipelineResult:
    detection: DetectionResult
    hosted_reader: ReaderBatchResult
    books: tuple[AnalyzedBook, ...]
    warnings: tuple[str, ...]
    review_items: tuple[ReviewItem, ...] = ()
    review_groups: tuple[ReviewGroup, ...] = ()
    crop_thumbnails: tuple[CropThumbnail, ...] = ()
