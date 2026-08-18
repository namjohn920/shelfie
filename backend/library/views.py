from PIL import Image, UnidentifiedImageError
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok'})


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
        with Image.open(uploaded_image) as image:
            image.load()
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        return Response(
            {'error': 'The uploaded file is not a valid image.'},
            status=HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            'status': 'received',
            'filename': uploaded_image.name,
            'content_type': uploaded_image.content_type,
            'width': width,
            'height': height,
        }
    )
