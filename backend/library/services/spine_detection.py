from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

from PIL import Image

from library.contracts.analysis import (
    BoundingBox,
    DetectionResult,
    DetectorTiming,
    SpineDetection,
)


DETR_CHECKPOINT = 'facebook/detr-resnet-50'
DETR_REVISION = 'no_timm'
DETECTION_THRESHOLD = 0.30
BOOK_LABEL = 'book'


class SpineDetectionError(RuntimeError):
    """Raised when the local detector cannot initialize or run inference."""


@dataclass(frozen=True)
class _LoadedDetr:
    processor: Any
    model: Any
    initial_load_seconds: float


@lru_cache(maxsize=1)
def _load_detr() -> _LoadedDetr:
    started = time.perf_counter()
    import torch
    from transformers import DetrForObjectDetection, DetrImageProcessor

    processor = DetrImageProcessor.from_pretrained(
        DETR_CHECKPOINT,
        revision=DETR_REVISION,
    )
    model = DetrForObjectDetection.from_pretrained(
        DETR_CHECKPOINT,
        revision=DETR_REVISION,
    ).to('cpu')
    model.eval()
    return _LoadedDetr(
        processor=processor,
        model=model,
        initial_load_seconds=time.perf_counter() - started,
    )


def sanitize_book_detections(
    raw_detections: Iterable[tuple[Sequence[float], float]],
    image_width: int,
    image_height: int,
) -> tuple[SpineDetection, ...]:
    """Clip ordinary DETR output values and assign deterministic spatial indices."""
    valid: list[tuple[BoundingBox, float]] = []
    for coordinates, confidence in raw_detections:
        if len(coordinates) != 4:
            continue
        coordinate_values = tuple(float(value) for value in coordinates)
        confidence_value = float(confidence)
        if not all(math.isfinite(value) for value in (*coordinate_values, confidence_value)):
            continue
        box = BoundingBox(*coordinate_values).clipped(
            image_width,
            image_height,
        )
        if box.width <= 0.0 or box.height <= 0.0:
            continue
        valid.append((box, confidence_value))

    valid.sort(
        key=lambda item: (
            item[0].top,
            item[0].left,
            item[0].bottom,
            item[0].right,
            -item[1],
        )
    )
    return tuple(
        SpineDetection(
            detection_index=index,
            box=box,
            confidence=confidence,
        )
        for index, (box, confidence) in enumerate(valid, start=1)
    )


def detect_book_spines(image: Image.Image) -> DetectionResult:
    """Detect COCO books on an upright PIL image using cached, CPU-only DETR."""
    total_started = time.perf_counter()
    model_was_cached = _load_detr.cache_info().currsize > 0
    try:
        loaded = _load_detr()
    except Exception as error:
        raise SpineDetectionError(
            'The local book detector could not be initialized.'
        ) from error

    try:
        import torch

        preprocess_started = time.perf_counter()
        inputs = loaded.processor(images=image, return_tensors='pt')
        inputs = {
            name: tensor.to('cpu') if hasattr(tensor, 'to') else tensor
            for name, tensor in inputs.items()
        }
        preprocess_seconds = time.perf_counter() - preprocess_started

        inference_started = time.perf_counter()
        with torch.inference_mode():
            outputs = loaded.model(**inputs)
        inference_seconds = time.perf_counter() - inference_started

        postprocess_started = time.perf_counter()
        target_sizes = torch.tensor([(image.height, image.width)], device='cpu')
        output = loaded.processor.post_process_object_detection(
            outputs=outputs,
            target_sizes=target_sizes,
            threshold=DETECTION_THRESHOLD,
        )[0]
        raw_books = []
        for box, score, label_id in zip(
            output['boxes'],
            output['scores'],
            output['labels'],
        ):
            label = str(loaded.model.config.id2label[int(label_id.item())])
            if label == BOOK_LABEL:
                raw_books.append((box.tolist(), float(score.item())))
        detections = sanitize_book_detections(
            raw_books,
            image_width=image.width,
            image_height=image.height,
        )
        postprocess_seconds = time.perf_counter() - postprocess_started
    except Exception as error:
        raise SpineDetectionError(
            'The local book detector could not analyze the image.'
        ) from error

    return DetectionResult(
        detections=detections,
        checkpoint=DETR_CHECKPOINT,
        threshold=DETECTION_THRESHOLD,
        image_width=image.width,
        image_height=image.height,
        timing=DetectorTiming(
            model_load_seconds=(
                0.0 if model_was_cached else loaded.initial_load_seconds
            ),
            preprocess_seconds=preprocess_seconds,
            inference_seconds=inference_seconds,
            postprocess_seconds=postprocess_seconds,
            total_seconds=time.perf_counter() - total_started,
            model_was_cached=model_was_cached,
        ),
    )
