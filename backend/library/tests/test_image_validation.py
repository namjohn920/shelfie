from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from library.services.image_validation import (
    ImageMetadata,
    InvalidImageError,
    validate_uploaded_image,
)


class ImageValidationTests(SimpleTestCase):
    def test_returns_metadata_after_decoding_image(self):
        image_bytes = BytesIO()
        Image.new('RGB', (24, 16), color='navy').save(image_bytes, format='JPEG')
        upload = SimpleUploadedFile(
            'bookshelf.jpg',
            image_bytes.getvalue(),
            content_type='image/jpeg',
        )

        result = validate_uploaded_image(upload)

        self.assertEqual(
            result,
            ImageMetadata(
                filename='bookshelf.jpg',
                content_type='image/jpeg',
                width=24,
                height=16,
            ),
        )

    def test_rejects_bytes_that_pillow_cannot_decode(self):
        upload = SimpleUploadedFile(
            'not-an-image.jpg',
            b'this is not an image',
            content_type='image/jpeg',
        )

        with self.assertRaises(InvalidImageError):
            validate_uploaded_image(upload)
