from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User
from payments.models import PaymentTransaction
from .forms import RecurringOrderForm
from .models import Cart, Order, ProducerOrder, RecurringOrder, RecurringOrderItem


BRISTOL_TIMEZONE = ZoneInfo("Europe/London")


def _masked_payment_reference(txn):
    reference = (txn.provider_reference or "").strip()
    if not reference:
        return "Not available"
    if len(reference) <= 4:
        return "*" * len(reference)
    return f"{'*' * (len(reference) - 4)}{reference[-4:]}"


def _parse_delivery_date(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _minimum_delivery_date():
    return timezone.now().astimezone(BRISTOL_TIMEZONE).date() + timedelta(days=2)


def _producer_display_name(producer):
    profile = getattr(producer, "producer_profile", None)
    business_name = getattr(profile, "business_name", "") if profile else ""
    return business_name or producer.username


def _format_decimal_quantity(value):
    if value is None:
        return "0"
    if hasattr(value, "quantize"):
        normalized = value.normalize()
        text = format(normalized, "f")
    else:
        text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def _quantity_with_unit(quantity, product):
    qty_text = _format_decimal_quantity(quantity)
    try:
        numeric_quantity = Decimal(str(quantity))
    except Exception:
        numeric_quantity = Decimal("0")

    if product.unit == product.Unit.EACH:
        unit = "item" if numeric_quantity == 1 else "items"
    elif product.unit == product.Unit.HEAD:
        unit = "head" if numeric_quantity == 1 else "heads"
    elif product.unit == product.Unit.L:
        unit = "litre" if numeric_quantity == 1 else "litres"
    else:
        unit = product.unit_label

    return f"{qty_text} {unit}"


def _stock_error_message(product):
    return (
        f"The quantity requested is not available. "
        f"Only {_format_decimal_quantity(product.stock)} left in stock "
        f"for {_producer_display_name(product.producer)}."
    )


def _build_delivery_address(profile):
    if not profile:
        return ""
    parts = [profile.organisation_name, profile.address_line1, profile.postcode]
    return "\n".join(part for part in parts if part)


def _group_items_by_producer(items, customer=None):
    grouped = OrderedDict()
    total_food_miles = Decimal("0.0")
    has_food_miles = False

    for item in items:
        product = item.product
        producer = product.producer
        producer_id = producer.id
        section = grouped.get(producer_id)
        if not section:
            profile = getattr(producer, "producer_profile", None)
            section = {
                "producer": producer,
                "producer_name": _producer_display_name(producer),
                "contact_phone": getattr(profile, "contact_phone", ""),
                "postcode": getattr(profile, "postcode", ""),
                "city": getattr(profile, "city", ""),
                "address_line1": getattr(profile, "address_line1", ""),
                "items": [],
                "subtotal": Decimal("0.00"),
            }
            grouped[producer_id] = section

        item.unit_label = product.unit_label
        item.unit_display = _quantity_with_unit(item.quantity, product)
        item.quantity_display = _quantity_with_unit(item.quantity, product)
        item.producer_name = section["producer_name"]
        if not hasattr(item, "unit_price"):
            item.unit_price = product.effective_price
        if not hasattr(item, "line_total"):
            item.line_total = (item.unit_price * item.quantity).quantize(Decimal("0.01"))
        if customer:
            item.food_miles = product.food_miles_for_customer(customer)
            if item.food_miles is not None:
                total_food_miles += Decimal(str(item.food_miles))
                has_food_miles = True

        section["items"].append(item)
        section["subtotal"] += item.line_total

    return list(grouped.values()), round(float(total_food_miles), 1), has_food_miles
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None



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
        producer_orders = list(o.producer_orders.select_related("producer", "producer__producer_profile"))
        o.producer_names = ", ".join(
            sorted({_producer_display_name(it.product.producer) for it in o.items.all() if it.product_id})
        )
        o.producer_status_entries = [
            {
                "name": _producer_display_name(po.producer),
                "status": po.status,
                "status_display": po.get_status_display(),
            }
            for po in producer_orders
        ]

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

    customer_profile = getattr(order.customer, "customer_profile", None)
    payment_transactions = list(
        PaymentTransaction.objects.filter(order=order).order_by("-id")
    )
    for txn in payment_transactions:
        txn.masked_reference = _masked_payment_reference(txn)

    producer_contacts = []
    seen_producers = set()
    for item in order.items.all():
        producer = item.product.producer
        if producer.id in seen_producers:
            continue
        seen_producers.add(producer.id)
        producer_contacts.append(producer)

    producer_sections, _, _ = _group_items_by_producer(order.items.all())
    producer_order_map = {po.producer_id: po for po in order.producer_orders.select_related("producer")}
    for section in producer_sections:
        producer_order = producer_order_map.get(section["producer"].id)
        section["producer_order"] = producer_order
        section["producer_status"] = producer_order.status if producer_order else ""
        section["producer_status_display"] = producer_order.get_status_display() if producer_order else "Pending"

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "customer_profile": customer_profile,
            "payment_transactions": payment_transactions,
            "producer_contacts": producer_contacts,
            "producer_sections": producer_sections,
        },
    )


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
    for txn in txns:
        txn.masked_reference = _masked_payment_reference(txn)
    producer_sections, _, _ = _group_items_by_producer(order.items.all())
    response = render(
        request,
        "orders/receipt.html",
        {
            "order": order,
            "txns": txns,
            "producer_sections": producer_sections,
            "customer_profile": getattr(order.customer, "customer_profile", None),
        },
    )

    
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

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    continue_url = request.session.get("last_product_list_url", "/shop/products/")

    cart_items = list(
        cart.items.select_related(
            "product",
            "product__producer",
            "product__category",
        )
    )

    producer_sections, total_food_miles, has_food_miles = _group_items_by_producer(
        cart_items,
        customer=request.user,
    )

    return render(
        request,
        "orders/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "producer_sections": producer_sections,
            "continue_url": continue_url,
            "total_food_miles": total_food_miles,
            "has_food_miles": has_food_miles,
            "customer_profile": getattr(request.user, "customer_profile", None),
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

    product = get_object_or_404(Product, id=product_id, is_active=True)

    if qty > product.stock:
        messages.error(request, _stock_error_message(product))
        next_url = request.POST.get("next") or request.GET.get("next") or "product_list"
        if isinstance(next_url, str) and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("product_list")

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    new_qty = qty if created else item.quantity + qty

    if new_qty > product.stock:
        messages.error(request, _stock_error_message(product))
    else:
        item.quantity = new_qty
        item.save()
        messages.success(
            request,
            f"Added {_quantity_with_unit(qty, product)} of {product.name} from "
            f"{_producer_display_name(product.producer)} to your cart."
        )

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
        messages.error(request, _stock_error_message(item.product))
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
def checkout_now(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    from .models import Cart, OrderItem, ProducerOrder

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    cart_items = list(
        cart.items.select_related(
            "product",
            "product__producer",
            "product__producer__producer_profile",
            "product__category",
        )
    )

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart_page")

    producer_sections, total_food_miles, has_food_miles = _group_items_by_producer(
        cart_items,
        customer=request.user,
    )
    customer_profile = getattr(request.user, "customer_profile", None)
    default_delivery_address = _build_delivery_address(customer_profile)
    commission_total = (cart.subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    order_total = (cart.subtotal + commission_total).quantize(Decimal("0.01"))
    minimum_delivery_date = _minimum_delivery_date()
    minimum_delivery_date_str = minimum_delivery_date.isoformat()
    minimum_delivery_date_label = minimum_delivery_date.strftime("%d %b %Y")

    if request.method == "GET":
        return render(
            request,
            "orders/checkout.html",
            {
                "cart": cart,
                "cart_items": cart_items,
                "producer_sections": producer_sections,
                "customer_profile": customer_profile,
                "default_delivery_address": default_delivery_address,
                "total_food_miles": total_food_miles,
                "has_food_miles": has_food_miles,
                "commission_total": commission_total,
                "order_total": order_total,
                "minimum_delivery_date": minimum_delivery_date_str,
                "minimum_delivery_date_label": minimum_delivery_date_label,
            },
        )

    for item in cart_items:
        if not item.product.is_active:
            messages.error(request, f"{item.product.name} is no longer available.")
            return redirect("checkout_now")
        if item.quantity > item.product.stock:
            messages.error(request, _stock_error_message(item.product))
            return redirect("checkout_now")

    delivery_address = (request.POST.get("delivery_address") or "").strip()
    raw_delivery_date = (request.POST.get("delivery_date") or "").strip()
    if not raw_delivery_date:
        messages.error(request, "Delivery date is required.")
        return redirect("checkout_now")

    delivery_date = _parse_delivery_date(raw_delivery_date)
    if raw_delivery_date and not delivery_date:
        messages.error(request, "Please choose a valid delivery date.")
        return redirect("checkout_now")
    if delivery_date and delivery_date < minimum_delivery_date:
        messages.error(request, "Please choose a delivery date at least 48 hours from today.")
        return redirect("checkout_now")

    if (
        customer_profile
        and customer_profile.account_type == customer_profile.AccountType.COMMUNITY_GROUP
        and not delivery_address
    ):
        messages.error(request, "Delivery address is required for community group orders.")
        return redirect("checkout_now")

    special_instructions = (request.POST.get("special_instructions") or "").strip()
    make_recurring = request.POST.get("make_recurring") == "on"
    recurring_name = (request.POST.get("recurring_name") or "").strip() or "Weekly Order"
    recurrence = (request.POST.get("recurrence") or "weekly").strip()
    order_day = (request.POST.get("order_day") or "monday").strip()
    delivery_day = (request.POST.get("delivery_day") or "wednesday").strip()

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            status=Order.Status.PENDING,
            delivery_address=delivery_address,
            delivery_date=delivery_date,
            special_instructions=special_instructions,
        )

        touched_producers = set()

        for item in cart_items:
            product = item.product
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.quantity,
                unit_price=product.effective_price,
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

        if (
            make_recurring
            and customer_profile
            and customer_profile.account_type == customer_profile.AccountType.RESTAURANT
        ):
            recurring_order = RecurringOrder.objects.create(
                customer=request.user,
                name=recurring_name,
                recurrence=recurrence,
                order_day=order_day,
                delivery_day=delivery_day,
                status=RecurringOrder.Status.ACTIVE,
            )
            recurring_order.schedule_next_delivery()
            recurring_order.save()

            for item in cart_items:
                RecurringOrderItem.objects.create(
                    recurring_order=recurring_order,
                    product=item.product,
                    quantity=item.quantity,
                )

        cart.items.all().delete()

    messages.success(request, "Checkout completed. Please complete payment.")
    return redirect("payment_page", order_id=order.id)


@login_required
def recurring_orders_page(request):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    recurring_orders = (
        RecurringOrder.objects.filter(customer=request.user)
        .prefetch_related("items__product__producer")
        .order_by("-created_at")
    )
    for recurring in recurring_orders:
        recurring.producer_sections, _, _ = _group_items_by_producer(recurring.items.all())
    return render(
        request,
        "orders/recurring_orders.html",
        {"recurring_orders": recurring_orders},
    )


@login_required
@require_POST
def recurring_order_toggle(request, recurring_order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    recurring_order = get_object_or_404(
        RecurringOrder,
        id=recurring_order_id,
        customer=request.user,
    )

    action = request.POST.get("action", "toggle")
    if action == "cancel":
        recurring_order.status = RecurringOrder.Status.CANCELLED
    elif action == "resume":
        recurring_order.status = RecurringOrder.Status.ACTIVE
        recurring_order.schedule_next_delivery()
    elif action == "pause":
        recurring_order.status = RecurringOrder.Status.PAUSED
    else:
        recurring_order.status = (
            RecurringOrder.Status.PAUSED
            if recurring_order.status == RecurringOrder.Status.ACTIVE
            else RecurringOrder.Status.ACTIVE
        )
        if recurring_order.status == RecurringOrder.Status.ACTIVE:
            recurring_order.schedule_next_delivery()
    recurring_order.save()
    messages.success(request, "Recurring order updated.")
    return redirect("recurring_orders")


@login_required
def recurring_order_edit(request, recurring_order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    recurring_order = get_object_or_404(
        RecurringOrder.objects.prefetch_related("items__product__producer"),
        id=recurring_order_id,
        customer=request.user,
    )
    if request.method == "POST":
        form = RecurringOrderForm(request.POST, instance=recurring_order)
        if form.is_valid():
            recurring_order = form.save(commit=False)
            if recurring_order.status == RecurringOrder.Status.ACTIVE:
                recurring_order.schedule_next_delivery()
            recurring_order.save()
            messages.success(request, "Recurring order details updated.")
            return redirect("recurring_orders")
    else:
        form = RecurringOrderForm(instance=recurring_order)

    recurring_order.producer_sections, _, _ = _group_items_by_producer(recurring_order.items.all())
    return render(
        request,
        "orders/recurring_order_edit.html",
        {"form": form, "recurring_order": recurring_order},
    )


@login_required
@require_POST
def recurring_order_load_to_cart(request, recurring_order_id):
    redirect_response = _customer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    recurring_order = get_object_or_404(
        RecurringOrder.objects.prefetch_related("items__product"),
        id=recurring_order_id,
        customer=request.user,
    )
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    from .models import CartItem

    for recurring_item in recurring_order.items.all():
        product = recurring_item.product
        if not product.is_active:
            continue
        qty = min(recurring_item.quantity, int(product.stock))
        if qty < 1:
            continue
        cart_item, _ = CartItem.objects.get_or_create(cart=cart, product=product)
        cart_item.quantity = qty
        cart_item.save()

    messages.success(request, "Recurring order copied to your cart. You can edit this week's quantities without changing the template.")
    return redirect("cart_page")




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
@login_required
@require_POST
def update_producer_order_status(request, producer_order_id):
    # Only producers can perform this action
    if getattr(request.user, "role", "") != User.Role.PRODUCER:
        return redirect("after_login")

    # Ensure the order belongs to THIS producer
    order = get_object_or_404(ProducerOrder, id=producer_order_id, producer=request.user)
    
    new_status = request.POST.get("status")
    if new_status in [ProducerOrder.Status.ACCEPTED, ProducerOrder.Status.CANCELLED]:
        order.status = new_status
        order.save()
        label = "accepted" if new_status == ProducerOrder.Status.ACCEPTED else "declined"
        messages.success(request, f"Order #{order.id} has been {label}.")
    
    return redirect("producer_orders")
