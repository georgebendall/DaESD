def cart_item_count(request):
    if not request.user.is_authenticated:
        return {"cart_item_count": 0}
    try:
        cart = getattr(request.user, "cart", None)
        if not cart:
            return {"cart_item_count": 0}
        return {"cart_item_count": cart.items.count()}
    except Exception:
        return {"cart_item_count": 0}