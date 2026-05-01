def cart_item_count(request):
    if not request.user.is_authenticated:
        return {"cart_item_count": 0}
    try:
        cart = getattr(request.user, "cart", None)
        if not cart:
            return {"cart_item_count": 0}
        return {
            "cart_item_count": sum(
                int(item.quantity or 0) for item in cart.items.only("quantity")
            )
        }
    except Exception:
        return {"cart_item_count": 0}
