from django.urls import path

from . import views

app_name = 'library'

urlpatterns = [
    path('health/', views.health, name='health'),
    path('analyze/', views.analyze, name='analyze'),
]
