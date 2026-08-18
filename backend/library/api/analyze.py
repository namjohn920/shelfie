from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_503_SERVICE_UNAVAILABLE

from library.services.image_validation import (
    InvalidImageError,
    decode_uploaded_image,
)
from library.services.spine_detection import (
    SpineDetectionError,
    detect_book_spines,
)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def analyze(request):
    uploaded_image = request.FILES.get('image')
    if uploaded_image is None:
        return Response(
            {'error': 'No image was provided.'},
            status=HTTP_400_BAD_REQUEST,
        )

    try:
        decoded_image = decode_uploaded_image(uploaded_image)
    except InvalidImageError:
        return Response(
            {'error': 'The uploaded file is not a valid image.'},
            status=HTTP_400_BAD_REQUEST,
        )

    try:
        detection_result = detect_book_spines(decoded_image.upright_image)
    except SpineDetectionError:
        return Response(
            {'error': 'The local book detector is temporarily unavailable.'},
            status=HTTP_503_SERVICE_UNAVAILABLE,
        )

    image_metadata = decoded_image.metadata

    return Response(
        {
            'status': 'received',
            'filename': image_metadata.filename,
            'content_type': image_metadata.content_type,
            'width': image_metadata.width,
            'height': image_metadata.height,
            'detection_count': len(detection_result.detections),
            'detections': [
                detection.as_dict() for detection in detection_result.detections
            ],
            'detector': {
                'checkpoint': detection_result.checkpoint,
                'threshold': detection_result.threshold,
                'coordinate_space': 'upright_image_pixels',
                'image_width': detection_result.image_width,
                'image_height': detection_result.image_height,
                'timing': detection_result.timing.as_dict(),
            },
        }
    )
