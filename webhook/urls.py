from django.urls import path
from . import views

urlpatterns = [
    path('webhook/radario/', views.radario_webhook, name='radario_webhook'),
    path('webhook/radario/klaster/', views.radario_webhook_klaster, name='radario_webhook_klaster'),
    path('health/', views.health_check, name='health_check'),
]