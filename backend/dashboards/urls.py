from django.urls import path
from .views import admin_dashboard, customer_dashboard, producer_dashboard, producer_stock, edit_stock_list # Add this import
from . import views # Add this import for the new product views

urlpatterns = [
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("customer-dashboard/", customer_dashboard, name="customer_dashboard"),
    #PRODUCER START--------------------------------------------------------------------------------
    path("producer-dashboard/", producer_dashboard, name="producer_dashboard"), # Add this line
    path("producer/stock/", producer_stock, name="producer_stock"),
    path("producer/edit-stock-list/", edit_stock_list, name="edit_stock_list"),
    # ADD THESE THREE LINES TO FIX THE ERROR:
    path("producer/add-product/", views.add_product, name="add_product"),
    path("producer/edit-product/<str:product_id>/", views.edit_product, name="edit_product"),
    path("producer/delete-product/<str:product_id>/", views.delete_product, name="delete_product"),
    path("producer/add-stock/<str:product_id>/", views.add_stock, name="add_stock"),
]
