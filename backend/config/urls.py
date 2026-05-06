from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import TemplateView
urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("", include("dashboards.urls")),
    path("orders/", include("orders.urls")),
    path("shop/", include("catalog.urls")),
    path("catalog/", include("catalog.urls")),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
