from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from library.contracts.analysis import (
    BoundingBox,
    DetectionResult,
    DetectorTiming,
    SpineDetection,
)
from library.services.spine_detection import SpineDetectionError


def fake_detection_result(
    detections: tuple[SpineDetection, ...] = (),
) -> DetectionResult:
    return DetectionResult(
        detections=detections,
        checkpoint='test-checkpoint',
        threshold=0.30,
        image_width=48,
        image_height=32,
        timing=DetectorTiming(
            model_load_seconds=0.0,
            preprocess_seconds=0.01,
            inference_seconds=0.02,
            postprocess_seconds=0.01,
            total_seconds=0.04,
            model_was_cached=True,
        ),
    )


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

    @patch('library.api.analyze.detect_book_spines')
    def test_analyze_returns_decoded_image_metadata(self, detect_book_spines):
        detect_book_spines.return_value = fake_detection_result()
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
                'detection_count': 0,
                'detections': [],
                'detector': {
                    'checkpoint': 'test-checkpoint',
                    'threshold': 0.3,
                    'coordinate_space': 'upright_image_pixels',
                    'image_width': 48,
                    'image_height': 32,
                    'timing': {
                        'model_load_seconds': 0.0,
                        'preprocess_seconds': 0.01,
                        'inference_seconds': 0.02,
                        'postprocess_seconds': 0.01,
                        'total_seconds': 0.04,
                        'model_was_cached': True,
                    },
                },
            },
        )
        self.assertEqual(detect_book_spines.call_count, 1)

    @patch('library.api.analyze.detect_book_spines')
    def test_analyze_serializes_fake_detection(self, detect_book_spines):
        detect_book_spines.return_value = fake_detection_result(
            (
                SpineDetection(
                    detection_index=1,
                    box=BoundingBox(1.25, 2.5, 20.75, 30.0),
                    confidence=0.87654321,
                ),
            )
        )
        image_bytes = BytesIO()
        Image.new('RGB', (48, 32), color='navy').save(image_bytes, format='JPEG')

        response = self.client.post(
            reverse('library:analyze'),
            {
                'image': SimpleUploadedFile(
                    'bookshelf.jpg',
                    image_bytes.getvalue(),
                    content_type='image/jpeg',
                )
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['detection_count'], 1)
        self.assertEqual(
            response.json()['detections'],
            [
                {
                    'detection_index': 1,
                    'label': 'book',
                    'confidence': 0.876543,
                    'box': {
                        'left': 1.25,
                        'top': 2.5,
                        'right': 20.75,
                        'bottom': 30.0,
                    },
                }
            ],
        )

    @patch('library.api.analyze.detect_book_spines')
    def test_analyze_translates_detector_failure(self, detect_book_spines):
        detect_book_spines.side_effect = SpineDetectionError('model failed')
        image_bytes = BytesIO()
        Image.new('RGB', (48, 32), color='navy').save(image_bytes, format='JPEG')

        response = self.client.post(
            reverse('library:analyze'),
            {
                'image': SimpleUploadedFile(
                    'bookshelf.jpg',
                    image_bytes.getvalue(),
                    content_type='image/jpeg',
                )
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.json(),
            {'error': 'The local book detector is temporarily unavailable.'},
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
