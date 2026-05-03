from django.urls import path
from . import views

urlpatterns = [
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/finance/", views.admin_finance_report, name="admin_finance_report"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("producer-dashboard/", views.producer_dashboard, name="producer_dashboard"),
    path("producer/settlements/", views.producer_settlements, name="producer_settlements"),

    path("producer/stock/", views.producer_stock, name="producer_stock"),
    path("producer/edit-stock-list/", views.edit_stock_list, name="edit_stock_list"),

    path("producer/add-product/", views.add_product, name="add_product"),
    path("producer/edit-product/<int:product_id>/", views.edit_product, name="edit_product"),
    path("producer/delete-product/<int:product_id>/", views.delete_product, name="delete_product"),
    path("producer/add-stock/<int:product_id>/", views.add_stock, name="add_stock"),
]
