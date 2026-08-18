from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from library.services.image_validation import (
    ImageMetadata,
    InvalidImageError,
    decode_uploaded_image,
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

    def test_preserves_stored_metadata_but_returns_exif_upright_pixels(self):
        image_bytes = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (20, 10), color='navy').save(
            image_bytes,
            format='JPEG',
            exif=exif,
        )
        upload = SimpleUploadedFile(
            'rotated-bookshelf.jpg',
            image_bytes.getvalue(),
            content_type='image/jpeg',
        )

        decoded = decode_uploaded_image(upload)

        self.assertEqual((decoded.metadata.width, decoded.metadata.height), (20, 10))
        self.assertEqual(decoded.upright_image.size, (10, 20))
