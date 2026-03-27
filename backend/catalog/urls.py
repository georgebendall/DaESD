from django.urls import path
from . import views

urlpatterns = [
    path("", views.product_list_page, name="product_list"),
    path("products/", views.product_list_page, name="product_list_products_alias"),
    path("product/<str:product_id>/", views.product_detail_page, name="product_detail"),
]