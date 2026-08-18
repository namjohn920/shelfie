from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from PIL import Image

from library.contracts.analysis import BoundingBox, SpineDetection


DEFAULT_CROP_PADDING_PIXELS = 8


@dataclass(frozen=True)
class SpineCrop:
    detection_index: int
    source_box: BoundingBox
    crop_box: BoundingBox
    confidence: float
    image: Image.Image


def create_spine_crops(
    image: Image.Image,
    detections: Iterable[SpineDetection],
    padding_pixels: int = DEFAULT_CROP_PADDING_PIXELS,
) -> tuple[SpineCrop, ...]:
    if padding_pixels < 0:
        raise ValueError('Crop padding cannot be negative.')

    crops: list[SpineCrop] = []
    for detection in detections:
        padded = BoundingBox(
            left=math.floor(detection.box.left - padding_pixels),
            top=math.floor(detection.box.top - padding_pixels),
            right=math.ceil(detection.box.right + padding_pixels),
            bottom=math.ceil(detection.box.bottom + padding_pixels),
        ).clipped(image.width, image.height)
        if padded.width <= 0.0 or padded.height <= 0.0:
            continue
        crop = image.crop(
            (
                int(padded.left),
                int(padded.top),
                int(padded.right),
                int(padded.bottom),
            )
        ).copy()
        crops.append(
            SpineCrop(
                detection_index=detection.detection_index,
                source_box=detection.box,
                crop_box=padded,
                confidence=detection.confidence,
                image=crop,
            )
        )
    return tuple(crops)
