from __future__ import annotations

from PIL import Image

from library.contracts.analysis import (
    AnalysisPipelineResult,
    AnalyzedBook,
    BookRead,
)
from library.services.book_reading import DEFAULT_MAX_WORKERS, read_book_crops
from library.services.catalog_matching import load_catalog, match_catalog
from library.services.crop_processing import (
    create_crop_thumbnails,
    create_spine_crops,
)
from library.services.result_consolidation import consolidate_review_items
from library.services.review_grouping import group_review_items
from library.services.review_policy import decide_review, user_visible_suggestion
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
    crop_thumbnails = create_crop_thumbnails(crops)
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
            analyzed_books.append(
                AnalyzedBook(
                    detection_index=crop_result.detection_index,
                    book_index=0,
                    read=None,
                    match=None,
                    review=decide_review(
                        None,
                        None,
                        reader_status=crop_result.status,
                    ),
                    crop_type=crop_result.crop_type,
                    region_type=crop_result.region_type,
                    region_text=crop_result.region_text,
                )
            )
            continue

        if crop_result.region_type == 'non_book':
            non_book_read = BookRead(
                title=None,
                raw_text=crop_result.region_text,
                readability=crop_result.readability or 'partial',
            )
            analyzed_books.append(
                AnalyzedBook(
                    detection_index=crop_result.detection_index,
                    book_index=0,
                    read=non_book_read,
                    match=None,
                    review=decide_review(
                        non_book_read,
                        None,
                        region_type=crop_result.region_type,
                    ),
                    crop_type=crop_result.crop_type,
                    region_type=crop_result.region_type,
                    region_text=crop_result.region_text,
                )
            )
            continue

        if not crop_result.books:
            empty_read = BookRead(
                title=None,
                raw_text=crop_result.region_text,
                readability=crop_result.readability or 'unreadable',
            )
            analyzed_books.append(
                AnalyzedBook(
                    detection_index=crop_result.detection_index,
                    book_index=0,
                    read=empty_read,
                    match=None,
                    review=decide_review(
                        empty_read,
                        None,
                        region_type=crop_result.region_type,
                    ),
                    crop_type=crop_result.crop_type,
                    region_type=crop_result.region_type,
                    region_text=crop_result.region_text,
                )
            )
            continue

        for book_index, book_read in enumerate(crop_result.books):
            match = None
            has_match_evidence = bool(book_read.title or book_read.author)
            if book_read.readability != 'unreadable' and has_match_evidence:
                if catalog is None:
                    catalog = load_catalog()
                match = match_catalog(book_read, catalog)
            review = decide_review(
                book_read,
                match,
                region_type=crop_result.region_type,
            )
            analyzed_books.append(
                AnalyzedBook(
                    detection_index=crop_result.detection_index,
                    book_index=book_index,
                    read=book_read,
                    match=match,
                    review=review,
                    suggested_match=user_visible_suggestion(book_read, match),
                    crop_type=crop_result.crop_type,
                    region_type=crop_result.region_type,
                    region_text=crop_result.region_text,
                )
            )

    raw_books = tuple(analyzed_books)
    review_items = consolidate_review_items(
        raw_books,
        detection.detections,
    )
    return AnalysisPipelineResult(
        detection=detection,
        hosted_reader=hosted_reader,
        books=raw_books,
        warnings=tuple(warnings),
        review_items=review_items,
        review_groups=group_review_items(review_items),
        crop_thumbnails=crop_thumbnails,
    )
