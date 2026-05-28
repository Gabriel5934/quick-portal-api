from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

from .views import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health, name='health'),
    path("", include("quickportal.urls")),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
