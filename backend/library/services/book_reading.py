from __future__ import annotations

import base64
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any

import requests

from library.contracts.analysis import (
    BookRead,
    CropReadResult,
    CropType,
    Readability,
    RegionType,
    ReaderBatchResult,
)
from library.services.crop_processing import SpineCrop


OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
MODEL_ID = 'qwen/qwen3-vl-8b-instruct'
REQUEST_TIMEOUT_SECONDS = 90
MAX_BOOKS_PER_CROP = 3
MAX_OUTPUT_TOKENS = 600
DEFAULT_MAX_WORKERS = 8
OPENROUTER_PROVIDER_PREFERENCES = {
    'require_parameters': True,
    'sort': 'latency',
}

CORE_PROMPT = (
    'You are reading a crop produced by a local bookshelf detector. The crop may '
    'contain one book, several books, a non-book object, only part of a spine, '
    'horizontal/rotated text, non-English text, or no usable book text. Classify '
    'region_type as book, multiple_books, non_book, or uncertain. Binders, notebooks, '
    'folders, boxes, signs, and labels may contain readable text without being books. '
    'If clearly not a book, use non_book, return no book entries, and preserve visible '
    'text in region_text. If book identity is uncertain, use uncertain. Never infer a '
    'book merely because familiar words appear. Extract only text supported by the '
    'image and do not guess from familiarity. Preserve original-language text. '
    'An author must be a person or organization explicitly credited as the author; '
    'publisher text, series labels, lecture/course labels, category labels, slogans, '
    'and unrelated nearby text are not authors. Authorship markers such as by, written '
    'by, 지음, 저, 저자, and 글 may establish authorship but must not be included in '
    'the returned author value. Return author null when authorship is uncertain. If a '
    'volume or book number is explicitly visible as a separate series identifier, put '
    'it in volume and keep the title clean: visible 21 plus 土地 means title 土地 and '
    'volume 21. Return volume null when no number is readable and never infer a missing '
    'number from series knowledge. Edition statements such as Second Edition, years, '
    'and numbers that are part of the title itself (for example 1984 or 1등의 통찰) '
    'are not volume identifiers. Return null for any other insufficient evidence.'
)

NULLABLE_STRING_SCHEMA = {
    'anyOf': [
        {'type': 'string'},
        {'type': 'null'},
    ]
}

EXTRACTION_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': [
        'crop_type',
        'region_type',
        'region_text',
        'readability',
        'books',
        'notes',
    ],
    'properties': {
        'crop_type': {
            'anyOf': [
                {
                    'type': 'string',
                    'enum': ['single_book', 'multiple_books', 'unreadable'],
                },
                {'type': 'null'},
            ],
        },
        'region_type': {
            'type': 'string',
            'enum': ['book', 'multiple_books', 'non_book', 'uncertain'],
        },
        'region_text': NULLABLE_STRING_SCHEMA,
        'readability': {
            'type': 'string',
            'enum': ['readable', 'partial', 'unreadable'],
        },
        'books': {
            'type': 'array',
            'maxItems': MAX_BOOKS_PER_CROP,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['title', 'author', 'volume', 'language', 'raw_text'],
                'properties': {
                    'title': NULLABLE_STRING_SCHEMA,
                    'author': NULLABLE_STRING_SCHEMA,
                    'volume': NULLABLE_STRING_SCHEMA,
                    'language': NULLABLE_STRING_SCHEMA,
                    'raw_text': NULLABLE_STRING_SCHEMA,
                },
            },
        },
        'notes': {'type': 'string'},
    },
}

_TERMINAL_KOREAN_CREDIT_MARKER = re.compile(r'\s+(?:지음|저자|저|글)\s*$')


class MissingApiKeyError(RuntimeError):
    """Raised before hosted work when OpenRouter is not configured."""


class _ResponseValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


def _crop_data_url(crop: SpineCrop) -> str:
    image_bytes = BytesIO()
    crop.image.convert('RGB').save(image_bytes, format='JPEG', quality=90)
    encoded = base64.b64encode(image_bytes.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


def _request_payload(crop: SpineCrop) -> dict[str, object]:
    return {
        'model': MODEL_ID,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': CORE_PROMPT},
                    {
                        'type': 'image_url',
                        'image_url': {'url': _crop_data_url(crop)},
                    },
                ],
            }
        ],
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': 'shelfie_crop_read',
                'strict': True,
                'schema': EXTRACTION_SCHEMA,
            },
        },
        'provider': OPENROUTER_PROVIDER_PREFERENCES,
        'temperature': 0,
        'max_tokens': MAX_OUTPUT_TOKENS,
        'stream': False,
        'usage': {'include': True},
    }


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_author(value: str | None) -> str | None:
    cleaned = _clean_optional_text(value)
    if cleaned is None:
        return None
    without_marker = _TERMINAL_KOREAN_CREDIT_MARKER.sub('', cleaned).strip()
    return without_marker or None


def _clean_volume(value: str | None, title: str | None) -> str | None:
    """Reject bounded false-volume shapes without extracting volume from a title."""
    cleaned = _clean_optional_text(value)
    if cleaned is None or re.search(r'\bedition\b', cleaned, flags=re.IGNORECASE):
        return None
    normalized_volume = unicodedata.normalize('NFKC', cleaned)
    normalized_title = unicodedata.normalize('NFKC', title or '').strip()
    if normalized_volume.isdigit() and normalized_title.startswith(normalized_volume):
        return None
    return cleaned


def _provider_error_present(response_body: dict[str, Any]) -> bool:
    if response_body.get('error') is not None:
        return True
    choices = response_body.get('choices')
    if not isinstance(choices, list) or not choices:
        return False
    choice = choices[0]
    if not isinstance(choice, dict):
        return False
    message = choice.get('message')
    return choice.get('error') is not None or (
        isinstance(message, dict) and message.get('error') is not None
    )


def _assistant_content(response_body: dict[str, Any]) -> dict[str, Any]:
    if _provider_error_present(response_body):
        raise _ResponseValidationError(
            'provider_error',
            'The hosted reader provider could not process this crop.',
        )

    choices = response_body.get('choices')
    if not isinstance(choices, list) or not choices:
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader returned no usable choice.',
        )
    choice = choices[0]
    if not isinstance(choice, dict):
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader returned an invalid choice.',
        )
    message = choice.get('message')
    if not isinstance(message, dict):
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader returned no assistant message.',
        )
    content = message.get('content')
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader returned no assistant content.',
        )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader returned malformed JSON.',
        ) from error
    if not isinstance(parsed, dict):
        raise _ResponseValidationError(
            'malformed_response',
            'The hosted reader JSON was not an object.',
        )
    return parsed


def _validated_books(
    extraction: dict[str, Any],
) -> tuple[
    CropType | None,
    RegionType,
    str | None,
    Readability,
    tuple[BookRead, ...],
    str | None,
]:
    required_fields = {
        'crop_type',
        'region_type',
        'region_text',
        'readability',
        'books',
        'notes',
    }
    if set(extraction) != required_fields:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader response did not match the required schema.',
        )

    crop_type = extraction['crop_type']
    if crop_type not in {None, 'single_book', 'multiple_books', 'unreadable'}:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned an invalid crop type.',
        )
    region_type = extraction['region_type']
    if region_type not in {'book', 'multiple_books', 'non_book', 'uncertain'}:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned an invalid region type.',
        )
    region_text = extraction['region_text']
    if region_text is not None and not isinstance(region_text, str):
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned invalid region text.',
        )
    readability = extraction['readability']
    if readability not in {'readable', 'partial', 'unreadable'}:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned an invalid readability value.',
        )
    notes = extraction['notes']
    if not isinstance(notes, str):
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned invalid notes.',
        )

    raw_books = extraction['books']
    if not isinstance(raw_books, list) or len(raw_books) > MAX_BOOKS_PER_CROP:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned an invalid number of books.',
        )
    if region_type == 'non_book' and raw_books:
        raise _ResponseValidationError(
            'invalid_schema',
            'The hosted reader returned book entries for a non-book region.',
        )

    books: list[BookRead] = []
    required_book_fields = {'title', 'author', 'volume', 'language', 'raw_text'}
    for raw_book in raw_books:
        if not isinstance(raw_book, dict) or set(raw_book) != required_book_fields:
            raise _ResponseValidationError(
                'invalid_schema',
                'The hosted reader returned an invalid book entry.',
            )
        if any(
            value is not None and not isinstance(value, str)
            for value in raw_book.values()
        ):
            raise _ResponseValidationError(
                'invalid_schema',
                'The hosted reader returned an invalid book text field.',
            )
        title = _clean_optional_text(raw_book['title'])
        books.append(
            BookRead(
                title=title,
                author=_clean_author(raw_book['author']),
                volume=_clean_volume(raw_book['volume'], title),
                language=_clean_optional_text(raw_book['language']),
                raw_text=_clean_optional_text(raw_book['raw_text']),
                readability=readability,
            )
        )

    return (
        crop_type,
        region_type,
        _clean_optional_text(region_text),
        readability,
        tuple(books),
        _clean_optional_text(notes),
    )


def _optional_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _optional_token_count(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _error_result(
    crop: SpineCrop,
    code: str,
    message: str,
    latency_seconds: float,
) -> CropReadResult:
    return CropReadResult(
        detection_index=crop.detection_index,
        crop_type=None,
        region_type=None,
        region_text=None,
        readability=None,
        books=(),
        status='error',
        error_code=code,
        error_message=message,
        latency_seconds=latency_seconds,
        cost_usd=None,
        model_id=MODEL_ID,
    )


def read_book_crop(crop: SpineCrop, *, api_key: str) -> CropReadResult:
    """Read one in-memory crop and translate every expected failure into a result."""
    try:
        payload = _request_payload(crop)
    except OSError:
        return _error_result(
            crop,
            'invalid_crop',
            'The detected crop could not be encoded.',
            0.0,
        )

    started = time.perf_counter()
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return _error_result(
            crop,
            'timeout',
            'The hosted reader timed out for this crop.',
            time.perf_counter() - started,
        )
    except requests.RequestException:
        return _error_result(
            crop,
            'http_error',
            'The hosted reader request failed for this crop.',
            time.perf_counter() - started,
        )
    latency_seconds = time.perf_counter() - started

    if not 200 <= response.status_code < 300:
        return _error_result(
            crop,
            'http_error',
            f'The hosted reader returned HTTP {response.status_code}.',
            latency_seconds,
        )

    try:
        response_body = response.json()
    except ValueError:
        return _error_result(
            crop,
            'malformed_response',
            'The hosted reader returned malformed JSON.',
            latency_seconds,
        )
    if not isinstance(response_body, dict):
        return _error_result(
            crop,
            'malformed_response',
            'The hosted reader response was not a JSON object.',
            latency_seconds,
        )

    try:
        extraction = _assistant_content(response_body)
        (
            crop_type,
            region_type,
            region_text,
            readability,
            books,
            notes,
        ) = _validated_books(extraction)
    except _ResponseValidationError as error:
        return _error_result(
            crop,
            error.code,
            error.safe_message,
            latency_seconds,
        )

    usage = response_body.get('usage')
    usage = usage if isinstance(usage, dict) else {}
    response_model = response_body.get('model')
    provider = response_body.get('provider')
    return CropReadResult(
        detection_index=crop.detection_index,
        crop_type=crop_type,
        region_type=region_type,
        region_text=region_text,
        readability=readability,
        books=books,
        status='ok',
        error_code=None,
        error_message=None,
        latency_seconds=latency_seconds,
        cost_usd=_optional_number(usage.get('cost')),
        model_id=response_model if isinstance(response_model, str) else MODEL_ID,
        provider=provider if isinstance(provider, str) else None,
        prompt_tokens=_optional_token_count(usage.get('prompt_tokens')),
        completion_tokens=_optional_token_count(usage.get('completion_tokens')),
        total_tokens=_optional_token_count(usage.get('total_tokens')),
        notes=notes,
    )


def read_book_crops(
    crops: tuple[SpineCrop, ...],
    *,
    api_key: str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> ReaderBatchResult:
    """Read crops concurrently while preserving one ordered result per crop."""
    if max_workers < 1:
        raise ValueError('Hosted reader max_workers must be at least 1.')

    started = time.perf_counter()
    if not crops:
        return ReaderBatchResult((), MODEL_ID, 0, 0, 0, 0.0, 0.0)

    resolved_api_key = api_key if api_key is not None else os.getenv('OPENROUTER_API_KEY')
    if not resolved_api_key or not resolved_api_key.strip():
        raise MissingApiKeyError('OPENROUTER_API_KEY is not configured.')
    resolved_api_key = resolved_api_key.strip()

    results: list[CropReadResult] = []
    worker_count = min(max_workers, len(crops))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        pending = {
            executor.submit(read_book_crop, crop, api_key=resolved_api_key): crop
            for crop in crops
        }
        for future in as_completed(pending):
            crop = pending[future]
            try:
                results.append(future.result())
            except Exception:
                results.append(
                    _error_result(
                        crop,
                        'internal_error',
                        'The hosted reader failed unexpectedly for this crop.',
                        0.0,
                    )
                )

    ordered_results = tuple(sorted(results, key=lambda result: result.detection_index))
    successful = sum(result.status == 'ok' for result in ordered_results)
    total_cost = sum(
        result.cost_usd
        for result in ordered_results
        if result.cost_usd is not None
    )
    return ReaderBatchResult(
        results=ordered_results,
        model_id=MODEL_ID,
        attempted_crops=len(crops),
        successful_crops=successful,
        failed_crops=len(crops) - successful,
        wall_seconds=time.perf_counter() - started,
        total_cost_usd=total_cost,
    )
