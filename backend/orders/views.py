# backend/orders/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User
from payments.models import PaymentTransaction
from .models import Order, ProducerOrder



def _customer_only_or_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if getattr(request.user, "role", "") != User.Role.CUSTOMER:
        return redirect("after_login")
    return None


def _producer_only_or_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if getattr(request.user, "role", "") != User.Role.PRODUCER:
        return redirect("after_login")
    return None




@login_required
def order_history_page(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    orders_qs = (
        Order.objects.filter(customer=request.user)
        .prefetch_related("items__product__producer", "items__product")
        .order_by("-created_at")
    )

 
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")
    producer_id = request.GET.get("producer")

    if date_from:
        orders_qs = orders_qs.filter(created_at__date__gte=date_from)
    if date_to:
        orders_qs = orders_qs.filter(created_at__date__lte=date_to)
    if producer_id:
        orders_qs = orders_qs.filter(items__product__producer_id=producer_id).distinct()

    orders = list(orders_qs)

   
    for o in orders:
        o.producer_names = ", ".join(
            sorted({it.product.producer.username for it in o.items.all() if it.product_id})
        )

    producers = (
        User.objects.filter(
            role=User.Role.PRODUCER,
            products__order_items__order__customer=request.user,
        )
        .distinct()
        .order_by("username")
    )

    return render(
        request,
        "orders/order_history.html",
        {
            "orders": orders,
            "producers": producers,
            "filters": {"from": date_from or "", "to": date_to or "", "producer": producer_id or ""},
        },
    )


@login_required
def order_detail_page(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product__producer", "items__product"),
        id=order_id,
    )

    if (
        order.customer != request.user
        and not request.user.is_staff
        and getattr(request.user, "role", "") != User.Role.ADMIN
    ):
        return redirect("after_login")

    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def reorder_order(request, order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import Cart, CartItem

    previous = get_object_or_404(Order, id=order_id, customer=request.user)
    cart, _ = Cart.objects.get_or_create(customer=request.user)

    added_any = False
    skipped = []

    for old_item in previous.items.select_related("product"):
        product = old_item.product
        if not product:
            continue

        
        if not product.is_active or product.stock <= 0:
            skipped.append(product.name)
            continue

        qty = min(old_item.quantity, product.stock)

        cart_item, _ = CartItem.objects.get_or_create(cart=cart, product=product)
        cart_item.quantity = min(cart_item.quantity + qty, product.stock)
        cart_item.save()
        added_any = True

    if skipped:
        messages.warning(
            request,
            "Some items could not be added (unavailable/out of stock): " + ", ".join(skipped)
        )

    if added_any:
        messages.success(request, "Reorder added available items to your cart.")
    else:
        messages.error(request, "No items could be reordered (all unavailable/out of stock).")

    return redirect("cart_page")


@login_required
def order_receipt(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product__producer", "items__product"),
        id=order_id,
    )

    if (
        order.customer != request.user
        and not request.user.is_staff
        and getattr(request.user, "role", "") != User.Role.ADMIN
    ):
        return redirect("after_login")

    txns = PaymentTransaction.objects.filter(order=order).order_by("-id")
    response = render(request, "orders/receipt.html", {"order": order, "txns": txns})

    
    if request.GET.get("download") == "1":
        response["Content-Disposition"] = f'attachment; filename="receipt-order-{order.id}.html"'

    return response




@login_required
def payment_page(request, order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    order = get_object_or_404(Order, id=order_id, customer=request.user)

    if request.method == "POST":
        PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.SUCCEEDED,
            provider="manual",
            currency="GBP",
        )
        order.status = Order.Status.PAID
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
    continue_url = request.session.get("last_product_list_url", "/shop/")
    return render(request, "orders/cart.html", {"cart": cart, "continue_url": continue_url})


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

    product = get_object_or_404(Product, id=product_id, is_active=True)

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
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)

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
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart_page")


@login_required
@require_POST
def checkout_now(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import Cart, OrderItem, ProducerOrder

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
            messages.error(request, f"Only {item.product.stock} left in stock for {item.product.name}.")
            return redirect("cart_page")

    order = Order.objects.create(customer=request.user, status=Order.Status.PENDING)

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




@login_required
def producer_orders_page(request):
    if getattr(request.user, "role", "") != User.Role.PRODUCER:
        return redirect("after_login")

    producer_orders = (
        ProducerOrder.objects
        .filter(producer=request.user)
        .select_related("parent_order", "parent_order__customer")
        .order_by("-created_at")
    )

    return render(
        request,
        "orders/producer_orders.html",
        {"producer_orders": producer_orders},
    )


@login_required
def producer_order_detail_page(request, producer_order_id):
    is_admin = request.user.is_staff or getattr(request.user, "role", "") == User.Role.ADMIN

    if is_admin:
        producer_order = get_object_or_404(ProducerOrder, id=producer_order_id)
    else:
        if getattr(request.user, "role", "") != User.Role.PRODUCER:
            return redirect("after_login")
        producer_order = get_object_or_404(
            ProducerOrder,
            id=producer_order_id,
            producer=request.user,   
        )

    items = (
        producer_order.parent_order.items
        .filter(product__producer=producer_order.producer)
        .select_related("product")
    )

    return render(
        request,
        "orders/producer_order_detail.html",
        {"producer_order": producer_order, "items": items},
    )