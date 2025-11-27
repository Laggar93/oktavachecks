from django.urls import path
from . import views

urlpatterns = [
    path('webhook/radario/', views.radario_webhook, name='radario_webhook'),
    path('health/', views.health_check, name='health_check'),
]