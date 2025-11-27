from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from oktavachecks import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('webhook.urls')),
    path('', include('main.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)