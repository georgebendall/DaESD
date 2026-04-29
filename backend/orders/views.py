from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User
from payments.models import PaymentTransaction
from .models import Order, Cart

try:
    from bson import ObjectId
except Exception:
    ObjectId = None


def _maybe_objectid(value: str):
    if ObjectId is None:
        return value
    try:
        return ObjectId(value)
    except Exception:
        raise Http404("Invalid id format")


def _customer_only_or_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if getattr(request.user, "role", "") != User.Role.CUSTOMER:
        return redirect("after_login")
    return None


@login_required
def order_detail_page(request, order_id):
    oid = _maybe_objectid(order_id)
    order = get_object_or_404(Order, id=oid)

    if order.customer != request.user and not request.user.is_staff and getattr(request.user, "role", "") != User.Role.ADMIN:
        return redirect("after_login")

    return render(request, "orders/order_detail.html", {"order": order})


@login_required
def payment_page(request, order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    oid = _maybe_objectid(order_id)
    order = get_object_or_404(Order, id=oid, customer=request.user)

    if request.method == "POST":
        PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.SUCCEEDED,
            provider="manual",
            currency="GBP",
        )

        order.status = "paid"
        order.save()

        messages.success(request, "Payment completed successfully.")
        return redirect("order_detail", order_id=order.id)

    return render(request, "orders/payment_page.html", {"order": order})


@login_required
def cart_page(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import Cart

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    continue_url = request.session.get("last_product_list_url", "/shop/products/")

    cart_items = list(
        cart.items.select_related(
            "product",
            "product__producer",
            "product__category",
        )
    )

    total_food_miles = 0
    has_food_miles = False

    for item in cart_items:
        item.food_miles = item.product.food_miles_for_customer(request.user)

        if item.food_miles is not None:
            total_food_miles += item.food_miles
            has_food_miles = True

    return render(
        request,
        "orders/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "continue_url": continue_url,
            "total_food_miles": round(total_food_miles, 1),
            "has_food_miles": has_food_miles,
        },
    )

@login_required
@require_POST
def cart_add(request, product_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

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
    product = get_object_or_404(Product, id=pid, is_active=True)

    if qty > product.stock:
        messages.error(request, f"Only {product.stock} left in stock for {product.name}.")
        next_url = request.POST.get("next") or request.GET.get("next") or "product_list"
        if isinstance(next_url, str) and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("product_list")

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    new_qty = qty if created else item.quantity + qty

    if new_qty > product.stock:
        messages.error(request, f"You cannot add more than {product.stock} of {product.name}.")
    else:
        item.quantity = new_qty
        item.save()
        messages.success(request, f"Added {qty} × {product.name} to your cart.")

    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect("product_list")


@login_required
@require_POST
def cart_update(request, item_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

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
        messages.info(request, "Item removed from cart.")
    elif qty > item.product.stock:
        messages.error(request, f"Only {item.product.stock} left in stock for {item.product.name}.")
    else:
        item.quantity = qty
        item.save()
        messages.success(request, "Cart updated.")

    return redirect("cart_page")


@login_required
@require_POST
def cart_remove(request, item_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import CartItem

    iid = _maybe_objectid(item_id)
    item = get_object_or_404(CartItem, id=iid, cart__customer=request.user)
    item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart_page")


@login_required
@require_POST
def checkout_now(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import Cart, Order, OrderItem, ProducerOrder

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    cart_items = list(cart.items.select_related("product", "product__producer"))

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart_page")

    for item in cart_items:
        if not item.product.is_active:
            messages.error(request, f"{item.product.name} is no longer available.")
            return redirect("cart_page")

        if item.quantity > item.product.stock:
            messages.error(
                request,
                f"Only {item.product.stock} left in stock for {item.product.name}."
            )
            return redirect("cart_page")

    order = Order.objects.create(
        customer=request.user,
        status=Order.Status.PENDING,
    )

    touched_producers = set()

    for item in cart_items:
        product = item.product

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item.quantity,
            unit_price=product.price,
        )

        product.stock = product.stock - item.quantity
        product.save()

        touched_producers.add(product.producer_id)

    order.recalculate_totals()
    order.save()

    for producer_id in touched_producers:
        producer_order = ProducerOrder.objects.create(
            parent_order=order,
            producer_id=producer_id,
            status=ProducerOrder.Status.PENDING,
        )
        producer_order.recalculate_subtotal()
        producer_order.save()

    cart.items.all().delete()

    messages.success(request, "Checkout completed. Please complete payment.")
    return redirect("payment_page", order_id=order.id)