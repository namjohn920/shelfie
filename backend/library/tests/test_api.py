from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase


class ShelfieApiTests(APITestCase):
    def test_health_returns_ok(self):
        response = self.client.get(reverse('library:health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_analyze_rejects_missing_image(self):
        response = self.client.post(
            reverse('library:analyze'),
            {},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'error': 'No image was provided.'})

    def test_analyze_returns_decoded_image_metadata(self):
        image_bytes = BytesIO()
        Image.new('RGB', (48, 32), color='navy').save(image_bytes, format='JPEG')
        upload = SimpleUploadedFile(
            'bookshelf.jpg',
            image_bytes.getvalue(),
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                'status': 'received',
                'filename': 'bookshelf.jpg',
                'content_type': 'image/jpeg',
                'width': 48,
                'height': 32,
            },
        )

    def test_analyze_rejects_invalid_image_bytes(self):
        upload = SimpleUploadedFile(
            'not-an-image.jpg',
            b'this is not an image',
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'error': 'The uploaded file is not a valid image.'},
        )
