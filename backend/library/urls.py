from django.urls import path

from .api.analyze import analyze
from .api.health import health
from .api.library import library_books

app_name = 'library'

urlpatterns = [
    path('health/', health, name='health'),
    path('analyze/', analyze, name='analyze'),
    path('library/', library_books, name='library'),
]
