# backend/backend/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("navigation.urls")),   # navigation app provides /api/route
]
