from django.urls import path
from .views import (
    cart_page,
    cart_add,
    cart_update,
    cart_remove,
    checkout_now,
    payment_page,
    order_detail_page,
    order_history_page,
    reorder_order,
    recurring_orders_page,
    recurring_order_toggle,
    recurring_order_edit,
    recurring_order_load_to_cart,
    order_receipt,
    producer_orders_page,
    producer_order_detail_page,
)

urlpatterns = [
    path("cart/", cart_page, name="cart_page"),
    path("cart/add/<int:product_id>/", cart_add, name="cart_add"),
    path("cart/update/<int:item_id>/", cart_update, name="cart_update"),
    path("cart/remove/<int:item_id>/", cart_remove, name="cart_remove"),
    path("checkout/", checkout_now, name="checkout_now"),

    path("history/", order_history_page, name="order_history"),
    path("recurring/", recurring_orders_page, name="recurring_orders"),
    path("recurring/<int:recurring_order_id>/toggle/", recurring_order_toggle, name="recurring_order_toggle"),
    path("recurring/<int:recurring_order_id>/edit/", recurring_order_edit, name="recurring_order_edit"),
    path("recurring/<int:recurring_order_id>/load-to-cart/", recurring_order_load_to_cart, name="recurring_order_load_to_cart"),
    path("<int:order_id>/", order_detail_page, name="order_detail"),
    path("<int:order_id>/payment/", payment_page, name="payment_page"),
    path("<int:order_id>/reorder/", reorder_order, name="order_reorder"),
    path("<int:order_id>/receipt/", order_receipt, name="order_receipt"),

    
    path("producer/orders/", producer_orders_page, name="producer_orders"),
    path("producer/<int:producer_order_id>/", producer_order_detail_page, name="producer_order_detail"),
]
