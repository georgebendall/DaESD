from django.urls import path, include

urlpatterns = [
    # Our registration pages first
    path("accounts/", include("accounts.urls")),

    # Built-in Django auth pages (login, logout, password reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),

    # App pages
    path("", include("dashboards.urls")),
    path("orders/", include("orders.urls")),
    path("shop/", include("catalog.urls")),
]