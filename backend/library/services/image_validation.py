from dataclasses import dataclass

from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError


class InvalidImageError(Exception):
    """Raised when Pillow cannot fully decode an uploaded image."""


@dataclass(frozen=True)
class ImageMetadata:
    filename: str
    content_type: str | None
    width: int
    height: int


def validate_uploaded_image(uploaded_image: UploadedFile) -> ImageMetadata:
    try:
        with Image.open(uploaded_image) as image:
            image.load()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError from error

    return ImageMetadata(
        filename=uploaded_image.name,
        content_type=uploaded_image.content_type,
        width=width,
        height=height,
    )
