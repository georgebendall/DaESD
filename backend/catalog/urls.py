from django.urls import path
from . import views
from reviews.views import create_review

urlpatterns = [
    path("", views.product_list_page, name="product_list"),
    path("products/", views.product_list_page, name="product_list_products_alias"),
    path("surplus/", views.surplus_deals_page, name="surplus_deals"),
    path("product/<int:product_id>/", views.product_detail_page, name="product_detail"),
    path("product/<int:product_id>/review/", create_review, name="product_review_create"),
]
