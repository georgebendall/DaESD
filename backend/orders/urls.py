from django.urls import path
from .views import order_detail_page, payment_page

urlpatterns = [
    path("<str:order_id>/", order_detail_page, name="order_detail"),
    path("<str:order_id>/pay/", payment_page, name="payment_page"),
]