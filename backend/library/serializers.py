from rest_framework import serializers

from library.models import LibraryBook
from library.services.catalog_matching import load_catalog


class LibraryBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryBook
        fields = ('id', 'catalog_id', 'title', 'author', 'source', 'created_at')


class LibraryBookCreateSerializer(serializers.Serializer):
    catalog_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=32,
        trim_whitespace=True,
    )
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=300,
        trim_whitespace=True,
    )
    author = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=300,
        trim_whitespace=True,
    )

    def validate(self, attributes):
        catalog_id = attributes.get('catalog_id') or None
        if catalog_id:
            catalog_entry = next(
                (
                    entry
                    for entry in load_catalog()
                    if entry.catalog_id == catalog_id
                ),
                None,
            )
            if catalog_entry is None:
                raise serializers.ValidationError(
                    {'catalog_id': 'Unknown catalog ID.'}
                )
            return {
                'catalog_id': catalog_entry.catalog_id,
                'title': catalog_entry.title,
                'author': catalog_entry.author,
                'source': LibraryBook.Source.CATALOG,
            }

        title = attributes.get('title') or ''
        if not title:
            raise serializers.ValidationError(
                {'title': 'A title is required for a manual book.'}
            )
        return {
            'catalog_id': None,
            'title': title,
            'author': attributes.get('author') or None,
            'source': LibraryBook.Source.MANUAL,
        }

    def create(self, validated_data):
        return LibraryBook.objects.create(**validated_data)
