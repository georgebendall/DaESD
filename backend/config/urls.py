# config/urls.py
from django.urls import path, include

urlpatterns = [
    # Built-in Django auth pages (login, logout, reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),

    # Your own accounts routes (after-login redirect)
    path("accounts/", include("accounts.urls")),

    # Your project pages
    path("", include("dashboards.urls")),
    path("orders/", include("orders.urls")),
    path("shop/", include("catalog.urls")),
]