from django.urls import path

from .api.analyze import analyze
from .api.health import health

app_name = 'library'

urlpatterns = [
    path('health/', health, name='health'),
    path('analyze/', analyze, name='analyze'),
]
