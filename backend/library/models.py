from django.db import models


class LibraryBook(models.Model):
    class Source(models.TextChoices):
        CATALOG = 'catalog', 'Catalog'
        MANUAL = 'manual', 'Manual'

    catalog_id = models.CharField(max_length=32, null=True, blank=True)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
