from django.test import SimpleTestCase

from library.contracts.analysis import BoundingBox
from library.services.spine_detection import sanitize_book_detections


class SpineDetectionContractTests(SimpleTestCase):
    def test_clips_filters_and_spatially_indexes_boxes(self):
        detections = sanitize_book_detections(
            [
                ((80, 10, 120, 70), 0.80),
                ((-5, -10, 15, 25), 0.95),
                ((20, 40, 20, 60), 0.99),
                ((30, 50, 28, 70), 0.70),
                ((10, 90, 40, 140), 0.60),
                ((float('nan'), 0, 10, 10), 0.88),
            ],
            image_width=100,
            image_height=100,
        )

        self.assertEqual([item.detection_index for item in detections], [1, 2, 3])
        self.assertEqual(detections[0].box, BoundingBox(0.0, 0.0, 15.0, 25.0))
        self.assertEqual(detections[1].box, BoundingBox(80.0, 10.0, 100.0, 70.0))
        self.assertEqual(detections[2].box, BoundingBox(10.0, 90.0, 40.0, 100.0))
