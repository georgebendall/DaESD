from django.urls import path
from .views import product_list_page

urlpatterns = [
    path("products/", product_list_page, name="product_list"),
]