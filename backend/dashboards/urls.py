from django.urls import path
from .views import admin_dashboard, customer_dashboard

urlpatterns = [
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("customer-dashboard/", customer_dashboard, name="customer_dashboard"),
]