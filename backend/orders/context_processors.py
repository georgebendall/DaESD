from catalog.models import Product
from orders.models import ProducerOrder


def cart_item_count(request):
    if not request.user.is_authenticated:
        return {
            "cart_item_count": 0,
            "producer_pending_orders_count": 0,
            "producer_low_stock_count": 0,
        }
    try:
        cart = getattr(request.user, "cart", None)
        cart_item_total = (
            sum(int(item.quantity or 0) for item in cart.items.only("quantity"))
            if cart
            else 0
        )

        producer_pending_orders_count = 0
        producer_low_stock_count = 0
        if getattr(request.user, "is_producer_user", False):
            producer_pending_orders_count = ProducerOrder.objects.filter(
                producer=request.user,
                status=ProducerOrder.Status.PENDING,
            ).count()
            producer_products = Product.objects.filter(producer=request.user).only(
                "stock",
                "stock_warning_level",
            )
            producer_low_stock_count = sum(1 for product in producer_products if product.is_low_stock)

        return {
            "cart_item_count": cart_item_total,
            "producer_pending_orders_count": producer_pending_orders_count,
            "producer_low_stock_count": producer_low_stock_count,
        }
    except Exception:
        return {
            "cart_item_count": 0,
            "producer_pending_orders_count": 0,
            "producer_low_stock_count": 0,
        }
