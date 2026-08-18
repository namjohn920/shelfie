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


@dataclass(frozen=True)
class BookRead:
    title: str | None
    author: str | None = None
    raw_text: str | None = None
    language: str | None = None
    readability: Readability = 'readable'


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


@dataclass(frozen=True)
class MatchCandidate:
    entry: CatalogEntry
    matched_title: str
    matched_author: str | None
    title_evidence: Literal['canonical', 'alternate', 'contained']
    title_score: float
    author_score: float | None
    combined_score: float


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
