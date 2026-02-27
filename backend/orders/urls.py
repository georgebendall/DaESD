from django.urls import path
from .views import order_detail_page, payment_page, cart_page, cart_add, cart_update,cart_remove

urlpatterns = [
     # Cart
    path("cart/", cart_page, name="cart_page"),
    path("cart/add/<str:product_id>/", cart_add, name="cart_add"),
    path("cart/update/<str:item_id>/", cart_update, name="cart_update"),
    path("cart/remove/<str:item_id>/", cart_remove, name="cart_remove"),
    
    path("<str:order_id>/", order_detail_page, name="order_detail"),
    path("<str:order_id>/pay/", payment_page, name="payment_page"),
]