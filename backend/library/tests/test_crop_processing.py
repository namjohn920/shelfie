import base64
from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image

from library.contracts.analysis import BoundingBox, SpineDetection
from library.services.crop_processing import (
    THUMBNAIL_LONGEST_SIDE_PIXELS,
    create_crop_thumbnails,
    create_spine_crops,
)


class CropProcessingTests(SimpleTestCase):
    def test_applies_padding_clips_bounds_and_preserves_detection_evidence(self):
        source = Image.new('RGB', (100, 80), color='navy')
        detection = SpineDetection(
            detection_index=7,
            box=BoundingBox(2.4, 3.2, 95.1, 78.5),
            confidence=0.82,
        )

        crops = create_spine_crops(source, [detection], padding_pixels=8)

        self.assertEqual(len(crops), 1)
        self.assertEqual(crops[0].detection_index, 7)
        self.assertEqual(crops[0].source_box, detection.box)
        self.assertEqual(crops[0].crop_box, BoundingBox(0.0, 0.0, 100.0, 80.0))
        self.assertEqual(crops[0].image.size, (100, 80))

    def test_rejects_negative_padding(self):
        with self.assertRaisesMessage(ValueError, 'Crop padding cannot be negative.'):
            create_spine_crops(Image.new('RGB', (10, 10)), [], padding_pixels=-1)

    def test_thumbnail_is_small_jpeg_and_created_once_per_detection(self):
        source = Image.new('RGB', (800, 400), color='navy')
        detections = (
            SpineDetection(3, BoundingBox(0, 0, 400, 400), 0.9),
            SpineDetection(7, BoundingBox(400, 0, 800, 400), 0.8),
        )
        crops = create_spine_crops(source, detections, padding_pixels=0)

        thumbnails = create_crop_thumbnails(crops)

        self.assertEqual(
            [thumbnail.detection_index for thumbnail in thumbnails],
            [3, 7],
        )
        for thumbnail in thumbnails:
            self.assertTrue(thumbnail.data_url.startswith('data:image/jpeg;base64,'))
            encoded = thumbnail.data_url.split(',', maxsplit=1)[1]
            with Image.open(BytesIO(base64.b64decode(encoded))) as image:
                self.assertEqual(image.format, 'JPEG')
                self.assertLessEqual(max(image.size), THUMBNAIL_LONGEST_SIDE_PIXELS)
