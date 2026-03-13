from django.urls import path, include

urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("dashboards.urls")),
    path("orders/", include("orders.urls")),
    path("shop/", include("catalog.urls")),
]