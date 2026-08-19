from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from PIL import Image

from library.contracts.analysis import BoundingBox, CropThumbnail, SpineDetection


DEFAULT_CROP_PADDING_PIXELS = 8
THUMBNAIL_LONGEST_SIDE_PIXELS = 220
THUMBNAIL_JPEG_QUALITY = 55


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


def create_crop_thumbnails(
    crops: Iterable[SpineCrop],
    *,
    longest_side_pixels: int = THUMBNAIL_LONGEST_SIDE_PIXELS,
    jpeg_quality: int = THUMBNAIL_JPEG_QUALITY,
) -> tuple[CropThumbnail, ...]:
    """Create one small in-memory JPEG data URL for each detected crop."""
    if longest_side_pixels < 1:
        raise ValueError('Thumbnail longest side must be at least 1 pixel.')
    if not 1 <= jpeg_quality <= 95:
        raise ValueError('Thumbnail JPEG quality must be between 1 and 95.')

    thumbnails: list[CropThumbnail] = []
    for crop in crops:
        thumbnail = crop.image.convert('RGB').copy()
        thumbnail.thumbnail(
            (longest_side_pixels, longest_side_pixels),
            Image.Resampling.LANCZOS,
        )
        image_bytes = BytesIO()
        thumbnail.save(
            image_bytes,
            format='JPEG',
            quality=jpeg_quality,
            optimize=True,
        )
        encoded = base64.b64encode(image_bytes.getvalue()).decode('ascii')
        thumbnails.append(
            CropThumbnail(
                detection_index=crop.detection_index,
                data_url=f'data:image/jpeg;base64,{encoded}',
            )
        )
    return tuple(thumbnails)
