# config/urls.py
# This file is the "map" of URLs for your site.

from django.urls import path, include

urlpatterns = [
    # Built-in Django auth pages (login, logout, password reset, etc.)
    # This creates: /accounts/login/ and /accounts/logout/
    path("accounts/", include("django.contrib.auth.urls")),

    # Your own pages
    path("", include("dashboards.urls")),
]