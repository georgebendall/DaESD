from decimal import Decimal

# backend/dashboards/views.py
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from catalog.models import Product, ProductInventoryHistory
from orders.models import Order, ProducerOrder
from payments.models import PaymentTransaction, WeeklySettlement
from .forms import ProducerProductForm


def _admin_only_or_forbidden(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_staff and getattr(request.user, "role", "") != User.Role.ADMIN:
        return render(request, "dashboards/forbidden.html", status=403)
    return None


@login_required
def admin_dashboard(request):
    admin_guard = _admin_only_or_forbidden(request)
    if admin_guard:
        return admin_guard

    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    total_orders = Order.objects.count()

    customers_count = User.objects.filter(role=User.Role.CUSTOMER).count()
    producers_count = User.objects.filter(role=User.Role.PRODUCER).count()
    admins_count = User.objects.filter(role=User.Role.ADMIN).count()

    
    producer_list = list(
        User.objects.filter(role=User.Role.PRODUCER).order_by("username")
    )

    
    for p in producer_list:
        p.postcode_display = (
            getattr(p, "postcode", None)
            or getattr(p, "post_code", None)
            or getattr(p, "zip_code", None)
            or ""
        )

    
    recent_orders = list(
        Order.objects.select_related("customer")
        .prefetch_related("items__product__producer", "items__product")
        .order_by("-created_at")[:10]
    )
    for o in recent_orders:
        o.producer_names = ", ".join(
            sorted({it.product.producer.username for it in o.items.all() if it.product_id})
        )

    
    recent_producer_orders = (
        ProducerOrder.objects.select_related("producer", "parent_order")
        .order_by("-created_at")[:15]
    )

    total_commission = sum(
        Order.objects.filter(
            status__in=[Order.Status.PAID, Order.Status.PROCESSING, Order.Status.COMPLETED]
        ).values_list("commission_total", flat=True),
        Decimal("0.00"),
    )
    total_gross_sales = sum(
        WeeklySettlement.objects.values_list("gross_sales", flat=True),
        Decimal("0.00"),
    )
    payment_success_count = PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.SUCCEEDED
    ).count()

    context = {
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "customers_count": customers_count,
        "producers_count": producers_count,
        "admins_count": admins_count,
        "producer_list": producer_list,
        "recent_orders": recent_orders,
        "recent_producer_orders": recent_producer_orders,
        "total_commission": total_commission,
        "total_gross_sales": total_gross_sales,
        "payment_success_count": payment_success_count,
    }
    return render(request, "dashboards/admin_dashboard.html", context)


@login_required
def admin_finance_report(request):
    admin_guard = _admin_only_or_forbidden(request)
    if admin_guard:
        return admin_guard

    settlements = list(
        WeeklySettlement.objects.select_related("producer", "producer__producer_profile")
        .order_by("-period_end", "producer__username")
    )
    settled_orders = Order.objects.filter(
        status__in=[Order.Status.PAID, Order.Status.PROCESSING, Order.Status.COMPLETED]
    )
    transactions = list(
        PaymentTransaction.objects.select_related("order", "order__customer")
        .order_by("-created_at")[:20]
    )

    total_gross_sales = sum(
        (settlement.gross_sales for settlement in settlements),
        Decimal("0.00"),
    )
    total_commission = sum(
        (settlement.commission_total for settlement in settlements),
        Decimal("0.00"),
    )
    total_payout = sum(
        (settlement.payout_total for settlement in settlements),
        Decimal("0.00"),
    )

    producer_rows = []
    for settlement in settlements:
        profile = getattr(settlement.producer, "producer_profile", None)
        producer_rows.append(
            {
                "producer_name": getattr(profile, "business_name", "") or settlement.producer.username,
                "period_start": settlement.period_start,
                "period_end": settlement.period_end,
                "gross_sales": settlement.gross_sales,
                "commission_total": settlement.commission_total,
                "payout_total": settlement.payout_total,
                "status": settlement.get_status_display(),
            }
        )

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="brfn-commission-report.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Producer",
                "Period Start",
                "Period End",
                "Gross Sales",
                "Commission",
                "Payout",
                "Status",
            ]
        )
        for row in producer_rows:
            writer.writerow(
                [
                    row["producer_name"],
                    row["period_start"],
                    row["period_end"],
                    row["gross_sales"],
                    row["commission_total"],
                    row["payout_total"],
                    row["status"],
                ]
            )
        return response

    return render(
        request,
        "dashboards/admin_finance_report.html",
        {
            "producer_rows": producer_rows,
            "transactions": transactions,
            "settlement_count": len(producer_rows),
            "settled_order_count": settled_orders.count(),
            "total_gross_sales": total_gross_sales,
            "total_commission": total_commission,
            "total_payout": total_payout,
        },
    )

@login_required
def customer_dashboard(request):
    
    if getattr(request.user, "role", "") != User.Role.CUSTOMER:
        return redirect("after_login")

    products_count = Product.objects.filter(is_active=True).count()

    my_orders_qs = Order.objects.filter(customer=request.user).order_by("-created_at")
    my_orders_count = my_orders_qs.count()
    recent_orders = my_orders_qs[:5]

    
    cart_items = 0
    try:
        from orders.models import Cart, CartItem
        cart = Cart.objects.filter(customer=request.user).first()
        cart_items = (
            sum(item.quantity for item in CartItem.objects.filter(cart=cart))
            if cart
            else 0
        )
    except Exception:
        cart_items = 0

    context = {
        "products_count": products_count,
        "my_orders_count": my_orders_count,
        "cart_items": cart_items,
        "recent_orders": recent_orders,
    }
    return render(request, "dashboards/customer_dashboard.html", context)

def _producer_only_or_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if getattr(request.user, "role", "") != User.Role.PRODUCER:
        return redirect("after_login")
    return None


@login_required
def producer_dashboard(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    products_qs = (
        Product.objects.filter(producer=request.user)
        .select_related("category")
        .order_by("-updated_at")
    )

    low_stock_products = [p for p in products_qs if p.is_low_stock]
    settlements_qs = WeeklySettlement.objects.filter(producer=request.user).order_by("-period_end")
    latest_settlement = settlements_qs.first()

    context = {
        "products_count": products_qs.count(),
        "active_products_count": products_qs.filter(is_active=True).count(),
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products[:5],
        "recent_products": products_qs[:5],
        "latest_settlement": latest_settlement,
    }
    return render(request, "dashboards/producer_dashboard.html", context)


@login_required
def producer_settlements(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    settlements = (
        WeeklySettlement.objects.filter(producer=request.user)
        .order_by("-period_end", "-created_at")
    )

    total_payout = sum(
        (settlement.payout_total for settlement in settlements),
        start=Decimal("0.00"),
    )
    total_gross = sum(
        (settlement.gross_sales for settlement in settlements),
        start=Decimal("0.00"),
    )

    return render(
        request,
        "dashboards/producer_settlements.html",
        {
            "producer_profile": getattr(request.user, "producer_profile", None),
            "settlements": settlements,
            "total_payout": total_payout,
            "total_gross": total_gross,
        },
    )


@login_required
def producer_stock(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = (
        Product.objects.filter(producer=request.user)
        .select_related("category")
        .order_by("name")
    )
    return render(
        request,
        "dashboards/stock.html",
        {
            "products": products,
            "products_count": products.count(),
            "low_stock_count": len([p for p in products if p.is_low_stock]),
        },
    )


@login_required
def edit_stock_list(request):
    return redirect("producer_stock")


@login_required
def add_product(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        form = ProducerProductForm(request.POST, user=request.user)

        # keep producer safe
        form.instance.producer = request.user

        if form.is_valid():
            product = form.save(commit=False)
            product.producer = request.user
            product.save()
            form.save_m2m()

            messages.success(request, f"{product.name} was added successfully.")
            if product.is_low_stock:
                messages.warning(
                    request,
                    f"Low stock alert: {product.name} has only {product.stock} left.",
                )

            return redirect("producer_stock")
    else:
        form = ProducerProductForm(user=request.user)

    return render(
        request,
        "dashboards/product_form.html",
        {
            "form": form,
            "page_title": "Add Product",
            "submit_label": "Save Product",
            "mode": "add",
        },
    )


@login_required
def edit_product(request, product_id):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    product = get_object_or_404(Product, id=product_id, producer=request.user)
    old_stock = product.stock
    old_availability = product.availability_status

    if request.method == "POST":
        form = ProducerProductForm(request.POST, instance=product, user=request.user)
        form.instance.producer = request.user

        if form.is_valid():
            updated_product = form.save()

            if (
                old_stock != updated_product.stock
                or old_availability != updated_product.availability_status
            ):
                ProductInventoryHistory.objects.create(
                    product=updated_product,
                    changed_by=request.user,
                    old_stock=old_stock,
                    new_stock=updated_product.stock,
                    old_availability_status=old_availability,
                    new_availability_status=updated_product.availability_status,
                    note="Updated by producer from dashboard",
                )

            messages.success(request, f"{updated_product.name} was updated successfully.")
            if updated_product.is_low_stock:
                messages.warning(
                    request,
                    f"Low stock alert: {updated_product.name} has only {updated_product.stock} left.",
                )

            return redirect("producer_stock")
    else:
        form = ProducerProductForm(instance=product, user=request.user)

    return render(
        request,
        "dashboards/product_form.html",
        {
            "form": form,
            "product": product,
            "page_title": f"Edit Product: {product.name}",
            "submit_label": "Save Changes",
            "mode": "edit",
        },
    )


@login_required
@require_POST
def delete_product(request, product_id):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    product = get_object_or_404(Product, id=product_id, producer=request.user)
    product_name = product.name
    product.delete()

    messages.success(request, f"{product_name} was deleted.")
    return redirect("producer_stock")


@login_required
def add_stock(request, product_id):
    return redirect("edit_product", product_id=product_id)
