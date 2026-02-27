from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import Http404
from payments.models import PaymentTransaction
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages




def order_detail_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    return render(request, "orders/order_detail.html", {
        "order": order
    })
def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        # Simulate payment success
        PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.SUCCEEDED,  # use your enum
            provider="manual",
            currency="GBP",
        )

        order.status = "paid"
        order.save()

        return redirect("order_detail", order_id=order.id)

    return render(request, "orders/payment_page.html", {
        "order": order
    })

try:
    from bson import ObjectId
except Exception:
    ObjectId = None


def _maybe_objectid(value: str):
    """
    Your project uses Mongo-style ObjectIds for some models.
    This converts '65f1...' into ObjectId(...) when bson is available.
    If not, it returns the original string.
    """
    if ObjectId is None:
        return value
    try:
        return ObjectId(value)
    except Exception:
        raise Http404("Invalid id format")


@login_required
def cart_page(request):
    from .models import Cart  # local import to avoid circulars

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return render(request, "orders/cart.html", {"cart": cart})


@login_required
@require_POST
def cart_add(request, product_id):
    from .models import Cart, CartItem
    from catalog.models import Product

    cart, _ = Cart.objects.get_or_create(customer=request.user)

    qty = request.POST.get("quantity", "1")
    try:
        qty = int(qty)
        if qty < 1:
            qty = 1
    except Exception:
        qty = 1

    pid = _maybe_objectid(product_id)
    product = get_object_or_404(Product, id=pid)

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if created:
        item.quantity = qty
    else:
        item.quantity += qty
    item.save()

    messages.success(request, f"Added {qty} × {product.name} to your cart.")

    # ✅ redirect back to originating page if provided
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect("product_list")  # sensible fallback


@login_required
@require_POST
def cart_update(request, item_id):
    from .models import CartItem

    iid = _maybe_objectid(item_id)
    item = get_object_or_404(CartItem, id=iid, cart__customer=request.user)

    qty = request.POST.get("quantity", "1")
    try:
        qty = int(qty)
    except Exception:
        qty = 1

    if qty < 1:
        item.delete()
    else:
        item.quantity = qty
        item.save()

    return redirect("cart_page")


@login_required
@require_POST
def cart_remove(request, item_id):
    from .models import CartItem

    iid = _maybe_objectid(item_id)
    item = get_object_or_404(CartItem, id=iid, cart__customer=request.user)
    item.delete()
    return redirect("cart_page")