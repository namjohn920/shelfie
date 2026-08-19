from django.db import DatabaseError
from rest_framework.decorators import api_view
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from library.models import LibraryBook
from library.serializers import LibraryBookCreateSerializer, LibraryBookSerializer
from library.services.catalog_matching import CatalogError


@api_view(['GET', 'POST', 'DELETE'])
def library_books(request):
    if request.method == 'GET':
        books = LibraryBookSerializer(LibraryBook.objects.all(), many=True)
        return Response({'books': books.data}, status=HTTP_200_OK)

    if request.method == 'DELETE':
        try:
            _, deleted_by_model = LibraryBook.objects.all().delete()
        except DatabaseError:
            return Response(
                {'error': 'The library could not be cleared.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {'deleted': deleted_by_model.get(LibraryBook._meta.label, 0)},
            status=HTTP_200_OK,
        )

    try:
        payload = request.data
    except ParseError:
        return Response(
            {'error': 'Request body must be valid JSON.'},
            status=HTTP_400_BAD_REQUEST,
        )

    serializer = LibraryBookCreateSerializer(data=payload)
    try:
        is_valid = serializer.is_valid()
    except CatalogError:
        return Response(
            {'error': 'The local book catalog is temporarily unavailable.'},
            status=HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not is_valid:
        return Response(
            {'error': _first_error(serializer.errors)},
            status=HTTP_400_BAD_REQUEST,
        )

    try:
        book = serializer.save()
    except DatabaseError:
        return Response(
            {'error': 'The book could not be saved.'},
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(
        {'book': LibraryBookSerializer(book).data},
        status=HTTP_201_CREATED,
    )


def _first_error(errors) -> str:
    for messages in errors.values():
        if isinstance(messages, dict):
            return _first_error(messages)
        if messages:
            return str(messages[0])
    return 'The book details are invalid.'
