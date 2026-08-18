from __future__ import annotations

from PIL import Image

from library.contracts.analysis import (
    AnalysisPipelineResult,
    AnalyzedBook,
)
from library.services.book_reading import DEFAULT_MAX_WORKERS, read_book_crops
from library.services.catalog_matching import load_catalog, match_catalog
from library.services.crop_processing import create_spine_crops
from library.services.spine_detection import detect_book_spines


def analyze_image(
    image: Image.Image,
    *,
    api_key: str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> AnalysisPipelineResult:
    """Run Shelfie's detect, crop, read, and match stages for one upright image."""
    detection = detect_book_spines(image)
    crops = create_spine_crops(image, detection.detections)
    hosted_reader = read_book_crops(
        crops,
        api_key=api_key,
        max_workers=max_workers,
    )

    analyzed_books: list[AnalyzedBook] = []
    warnings: list[str] = []
    catalog = None

    for crop_result in hosted_reader.results:
        if crop_result.status == 'error':
            warnings.append(
                f'Detection {crop_result.detection_index}: '
                f'{crop_result.error_message}'
            )
            continue

        for book_index, book_read in enumerate(crop_result.books):
            match = None
            has_match_evidence = bool(book_read.title or book_read.author)
            if book_read.readability != 'unreadable' and has_match_evidence:
                if catalog is None:
                    catalog = load_catalog()
                match = match_catalog(book_read, catalog)
            analyzed_books.append(
                AnalyzedBook(
                    detection_index=crop_result.detection_index,
                    book_index=book_index,
                    read=book_read,
                    match=match,
                )
            )

    return AnalysisPipelineResult(
        detection=detection,
        hosted_reader=hosted_reader,
        books=tuple(analyzed_books),
        warnings=tuple(warnings),
    )
