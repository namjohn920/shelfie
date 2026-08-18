from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from library.services.image_validation import (
    InvalidImageError,
    validate_uploaded_image,
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
        image_metadata = validate_uploaded_image(uploaded_image)
    except InvalidImageError:
        return Response(
            {'error': 'The uploaded file is not a valid image.'},
            status=HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            'status': 'received',
            'filename': image_metadata.filename,
            'content_type': image_metadata.content_type,
            'width': image_metadata.width,
            'height': image_metadata.height,
        }
    )
