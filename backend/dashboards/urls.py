from django.urls import path
from .views import (
    admin_dashboard,
    customer_dashboard,
    producer_dashboard,
    producer_stock,
    edit_stock_list,
    add_product,
    edit_product,
    delete_product,
    add_stock,
)

urlpatterns = [
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("customer-dashboard/", customer_dashboard, name="customer_dashboard"),

    path("producer-dashboard/", producer_dashboard, name="producer_dashboard"),
    path("producer/stock/", producer_stock, name="producer_stock"),
    path("producer/edit-stock-list/", edit_stock_list, name="edit_stock_list"),

    path("producer/add-product/", add_product, name="add_product"),
    path("producer/edit-product/<str:product_id>/", edit_product, name="edit_product"),
    path("producer/delete-product/<str:product_id>/", delete_product, name="delete_product"),
    path("producer/add-stock/<str:product_id>/", add_stock, name="add_stock"),
]