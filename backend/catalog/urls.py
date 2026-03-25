from django.urls import path
from .views import product_detail_page, product_list_page

urlpatterns = [
    path("products/", product_list_page, name="product_list"),
    path("products/<str:product_id>/", product_detail_page, name="product_detail"),
]