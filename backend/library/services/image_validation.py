from dataclasses import dataclass

from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImageError(Exception):
    """Raised when Pillow cannot fully decode an uploaded image."""


@dataclass(frozen=True)
class ImageMetadata:
    filename: str
    content_type: str | None
    width: int
    height: int


@dataclass(frozen=True)
class DecodedImage:
    metadata: ImageMetadata
    upright_image: Image.Image


def decode_uploaded_image(uploaded_image: UploadedFile) -> DecodedImage:
    try:
        with Image.open(uploaded_image) as image:
            image.load()
            width, height = image.size
            upright_image = ImageOps.exif_transpose(image).convert('RGB').copy()
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError from error

    return DecodedImage(
        metadata=ImageMetadata(
            filename=uploaded_image.name,
            content_type=uploaded_image.content_type,
            width=width,
            height=height,
        ),
        upright_image=upright_image,
    )


def validate_uploaded_image(uploaded_image: UploadedFile) -> ImageMetadata:
    return decode_uploaded_image(uploaded_image).metadata
