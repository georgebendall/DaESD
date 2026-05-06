from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal

# backend/dashboards/views.py
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from catalog.models import Product, ProductInventoryHistory
from orders.models import Order, ProducerOrder
from payments.models import WeeklySettlement
from .forms import ProducerProductForm


COMMISSION_RATE = Decimal("0.05")
QUALIFYING_PARENT_STATUSES = [
    Order.Status.PAID,
    Order.Status.PROCESSING,
    Order.Status.COMPLETED,
]
QUALIFYING_PRODUCER_STATUSES = [
    ProducerOrder.Status.DISPATCHED,
    ProducerOrder.Status.COMPLETED,
]


def _settlement_period_for(day):
    period_start = day - timedelta(days=day.weekday())
    period_end = period_start + timedelta(days=6)
    return period_start, period_end


def _payment_status_for_period(settlement_record):
    if settlement_record and settlement_record.status == WeeklySettlement.Status.PAID:
        return "Processed"
    return "Pending Bank Transfer"


def _producer_settlement_data(producer):
    settlement_records = {
        (settlement.period_start, settlement.period_end): settlement
        for settlement in WeeklySettlement.objects.filter(producer=producer)
    }

    producer_orders = (
        ProducerOrder.objects.filter(
            producer=producer,
            status__in=QUALIFYING_PRODUCER_STATUSES,
            parent_order__status__in=QUALIFYING_PARENT_STATUSES,
        )
        .select_related("parent_order", "parent_order__customer", "producer__producer_profile")
        .prefetch_related("parent_order__items__product")
        .order_by("-parent_order__delivery_date", "-parent_order__created_at", "-id")
    )

    rows = []
    period_map = OrderedDict()
    ytd_gross = Decimal("0.00")
    ytd_commission = Decimal("0.00")
    ytd_payout = Decimal("0.00")
    current_year = timezone.localdate().year

    for producer_order in producer_orders:
        settlement_day = producer_order.parent_order.delivery_date or timezone.localtime(
            producer_order.parent_order.created_at
        ).date()
        period_start, period_end = _settlement_period_for(settlement_day)
        settlement_record = settlement_records.get((period_start, period_end))

        gross_amount = producer_order.subtotal.quantize(Decimal("0.01"))
        commission_amount = (gross_amount * COMMISSION_RATE).quantize(Decimal("0.01"))
        payout_amount = (gross_amount - commission_amount).quantize(Decimal("0.01"))

        item_rows = []
        item_descriptions = []
        for item in producer_order.parent_order.items.all():
            if item.product.producer_id != producer.id:
                continue
            item_rows.append(
                {
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "unit": item.product.unit_label,
                }
            )
            item_descriptions.append(
                f"{item.product.name} ({item.quantity} {item.product.unit_label})"
            )

        row = {
            "period_start": period_start,
            "period_end": period_end,
            "order_id": producer_order.parent_order.id,
            "order_date": settlement_day,
            "customer_label": producer_order.parent_order.customer.username,
            "items": item_rows,
            "items_csv": "; ".join(item_descriptions),
            "gross_amount": gross_amount,
            "commission_amount": commission_amount,
            "payout_amount": payout_amount,
            "payment_status": _payment_status_for_period(settlement_record),
        }
        rows.append(row)

        period_key = (period_start, period_end)
        if period_key not in period_map:
            period_map[period_key] = {
                "period_start": period_start,
                "period_end": period_end,
                "gross_amount": Decimal("0.00"),
                "commission_amount": Decimal("0.00"),
                "payout_amount": Decimal("0.00"),
                "payment_status": _payment_status_for_period(settlement_record),
                "orders": [],
            }

        period_summary = period_map[period_key]
        period_summary["gross_amount"] += gross_amount
        period_summary["commission_amount"] += commission_amount
        period_summary["payout_amount"] += payout_amount
        period_summary["orders"].append(row)

        if period_end.year == current_year:
            ytd_gross += gross_amount
            ytd_commission += commission_amount
            ytd_payout += payout_amount

    period_summaries = list(period_map.values())
    latest_summary = period_summaries[0] if period_summaries else None

    return {
        "rows": rows,
        "period_summaries": period_summaries,
        "latest_summary": latest_summary,
        "ytd_gross": ytd_gross.quantize(Decimal("0.01")),
        "ytd_commission": ytd_commission.quantize(Decimal("0.01")),
        "ytd_payout": ytd_payout.quantize(Decimal("0.01")),
    }


def _admin_only_or_forbidden(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_staff and getattr(request.user, "role", "") != User.Role.ADMIN:
        return render(request, "dashboards/forbidden.html", status=403)
    return None


def _order_report_date(order):
    # Finance reports are based on the delivery window when available so
    # admin and producer views line up with settlement periods.
    return order.delivery_date or timezone.localtime(order.created_at).date()


def _order_payment_details(order):
    transaction = order.payment_transactions.order_by("-created_at").first()
    if not transaction:
        return {
            "status": "Not recorded",
            "reference": "Not recorded",
        }
    return {
        "status": transaction.get_status_display(),
        "reference": transaction.provider_reference or "Not recorded",
    }


def _producer_payment_breakdown(order):
    breakdown = []
    qualifying_statuses = {
        ProducerOrder.Status.DISPATCHED,
        ProducerOrder.Status.COMPLETED,
    }
    for producer_order in order.producer_orders.select_related("producer", "producer__producer_profile").all():
        gross_amount = producer_order.subtotal.quantize(Decimal("0.01"))
        payout_amount = (gross_amount * (Decimal("1.00") - COMMISSION_RATE)).quantize(Decimal("0.01"))
        breakdown.append(
            {
                "producer_name": getattr(
                    getattr(producer_order.producer, "producer_profile", None),
                    "business_name",
                    "",
                )
                or producer_order.producer.username,
                "status": producer_order.get_status_display(),
                "status_value": producer_order.status,
                "gross_amount": gross_amount,
                "payout_amount": payout_amount,
                "is_qualifying": producer_order.status in qualifying_statuses,
            }
        )
    return breakdown


def _admin_finance_report_rows(date_from=None, date_to=None, producer_id="", order_status=""):
    all_producer_choices = [
        getattr(getattr(user, "producer_profile", None), "business_name", "") or user.username
        for user in User.objects.filter(role=User.Role.PRODUCER).select_related("producer_profile").order_by("username")
    ]
    qualifying_statuses = [
        Order.Status.PAID,
        Order.Status.PROCESSING,
        Order.Status.COMPLETED,
    ]
    orders = (
        Order.objects.filter(status__in=qualifying_statuses)
        .select_related("customer")
        .prefetch_related(
            "items__product",
            "producer_orders__producer",
            "producer_orders__producer__producer_profile",
            "payment_transactions",
        )
        .order_by("-delivery_date", "-created_at", "-id")
    )

    rows = []
    producer_choices = OrderedDict()
    total_order_value = Decimal("0.00")
    total_commission = Decimal("0.00")
    total_payout = Decimal("0.00")
    order_count = 0
    ytd_commission = Decimal("0.00")
    current_year = timezone.localdate().year

    for order in orders:
        order_date = _order_report_date(order)
        if date_from and order_date < date_from:
            continue
        if date_to and order_date > date_to:
            continue
        if order_status and order.status != order_status:
            continue

        producer_breakdown = _producer_payment_breakdown(order)
        reportable_statuses = {
            ProducerOrder.Status.DISPATCHED,
            ProducerOrder.Status.COMPLETED,
            ProducerOrder.Status.CANCELLED,
        }
        for producer_entry in producer_breakdown:
            producer_choices[producer_entry["producer_name"]] = producer_entry["producer_name"]

        if producer_id:
            matching_breakdown = [entry for entry in producer_breakdown if entry["producer_name"] == producer_id]
            matching_breakdown = [
                entry for entry in matching_breakdown if entry["status_value"] in reportable_statuses
            ]
            if not matching_breakdown:
                continue
        else:
            if not producer_breakdown or any(
                entry["status_value"] not in reportable_statuses for entry in producer_breakdown
            ):
                continue
            matching_breakdown = producer_breakdown

        gross_amount = order.subtotal.quantize(Decimal("0.01"))
        commission_amount = (gross_amount * COMMISSION_RATE).quantize(Decimal("0.01"))
        payout_amount = (gross_amount - commission_amount).quantize(Decimal("0.01"))
        payment_details = _order_payment_details(order)
        items_summary = "; ".join(
            f"{item.product.name} ({item.quantity} {item.product.unit_label})" for item in order.items.all()
        )

        row = {
            "order_id": order.id,
            "order_date": order_date,
            "customer_label": order.customer.username,
            "gross_amount": gross_amount,
            "commission_amount": commission_amount,
            "payout_amount": payout_amount,
            "status": order.get_status_display(),
            "status_value": order.status,
            "payment_status": payment_details["status"],
            "payment_reference": payment_details["reference"],
            "items_summary": items_summary,
            "producer_breakdown": matching_breakdown if producer_id else producer_breakdown,
        }
        rows.append(row)

        total_order_value += gross_amount
        total_commission += commission_amount
        total_payout += payout_amount
        order_count += 1
        if order_date.year == current_year:
            ytd_commission += commission_amount

    month_start = timezone.localdate().replace(day=1)
    monthly_rows = [row for row in rows if row["order_date"] >= month_start]
    monthly_commission_total = sum((row["commission_amount"] for row in monthly_rows), Decimal("0.00"))

    return {
        "rows": rows,
        "producer_choices": sorted(set(all_producer_choices) | set(producer_choices.keys())),
        "total_order_value": total_order_value.quantize(Decimal("0.01")),
        "total_commission": total_commission.quantize(Decimal("0.01")),
        "total_payout": total_payout.quantize(Decimal("0.01")),
        "order_count": order_count,
        "monthly_commission_total": monthly_commission_total.quantize(Decimal("0.01")),
        "ytd_commission_total": ytd_commission.quantize(Decimal("0.01")),
    }


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

    context = {
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "customers_count": customers_count,
        "producers_count": producers_count,
        "recent_orders": recent_orders,
        "recent_producer_orders": recent_producer_orders,
    }
    return render(request, "dashboards/admin_dashboard.html", context)


@login_required
def admin_finance_report(request):
    admin_guard = _admin_only_or_forbidden(request)
    if admin_guard:
        return admin_guard

    today = timezone.localdate()
    default_date_to = today
    default_date_from = today - timedelta(days=13)
    date_from_raw = (request.GET.get("from") or "").strip()
    date_to_raw = (request.GET.get("to") or "").strip()
    producer_filter = (request.GET.get("producer") or "").strip()
    order_status = (request.GET.get("order_status") or "").strip()
    order_id = (request.GET.get("order_id") or "").strip()

    try:
        date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date() if date_from_raw else default_date_from
    except ValueError:
        date_from = default_date_from
    try:
        date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date() if date_to_raw else default_date_to
    except ValueError:
        date_to = default_date_to

    report_data = _admin_finance_report_rows(
        date_from=date_from,
        date_to=date_to,
        producer_id=producer_filter,
        order_status=order_status,
    )
    rows = report_data["rows"]
    selected_order = next(
        (row for row in rows if order_id.isdigit() and row["order_id"] == int(order_id)),
        rows[0] if rows else None,
    )

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="brfn-commission-report.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Order Number",
                "Order Date",
                "Customer",
                "Order Gross",
                "Commission (5%)",
                "Total Producer Payout (95%)",
                "Order Status",
                "Payment Status",
                "Payment Reference",
                "Producer",
                "Producer Gross",
                "Producer Payout",
                "Producer Order Status",
                "Items",
            ]
        )
        for row in rows:
            for producer_row in row["producer_breakdown"]:
                writer.writerow(
                    [
                        row["order_id"],
                        row["order_date"],
                        row["customer_label"],
                        row["gross_amount"],
                        row["commission_amount"],
                        row["payout_amount"],
                        row["status"],
                        row["payment_status"],
                        row["payment_reference"],
                        producer_row["producer_name"],
                        producer_row["gross_amount"],
                        producer_row["payout_amount"],
                        producer_row["status"],
                        row["items_summary"],
                    ]
                )
        return response

    return render(
        request,
        "dashboards/admin_finance_report.html",
        {
            "report_rows": rows,
            "selected_order": selected_order,
            "total_order_value": report_data["total_order_value"],
            "total_commission": report_data["total_commission"],
            "total_payout": report_data["total_payout"],
            "order_count": report_data["order_count"],
            "monthly_commission_total": report_data["monthly_commission_total"],
            "ytd_commission_total": report_data["ytd_commission_total"],
            "producer_choices": report_data["producer_choices"],
            "filters": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "producer": producer_filter,
                "order_status": order_status,
                "order_id": order_id,
            },
            "order_status_choices": [
                Order.Status.PAID,
                Order.Status.PROCESSING,
                Order.Status.COMPLETED,
            ],
        },
    )

@login_required
def my_orders_page(request):
    
    if getattr(request.user, "role", "") != User.Role.CUSTOMER:
        return redirect("after_login")

    my_orders_qs = Order.objects.filter(customer=request.user).order_by("-created_at")
    my_orders_count = my_orders_qs.count()
    recent_orders = my_orders_qs[:5]
    recent_completed_orders = my_orders_qs.filter(status=Order.Status.COMPLETED).count()
    recent_pending_orders = my_orders_qs.exclude(status=Order.Status.COMPLETED).count()
    recurring_orders_count = request.user.recurring_orders.count()

    
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
        "my_orders_count": my_orders_count,
        "completed_orders_count": recent_completed_orders,
        "pending_orders_count": recent_pending_orders,
        "cart_items": cart_items,
        "recurring_orders_count": recurring_orders_count,
        "recent_orders": recent_orders,
    }
    return render(request, "orders/my_orders.html", context)

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
    settlement_data = _producer_settlement_data(request.user)
    pending_orders_count = ProducerOrder.objects.filter(
        producer=request.user,
        status=ProducerOrder.Status.PENDING,
    ).count()
    product_count = Product.objects.filter(producer=request.user).count()

    return render(
        request,
        "dashboards/producer_dashboard.html",
        {
            "producer_profile": getattr(request.user, "producer_profile", None),
            "pending_orders_count": pending_orders_count,
            "product_count": product_count,
            "latest_settlement": settlement_data["latest_summary"],
            "ytd_gross": settlement_data["ytd_gross"],
            "ytd_commission": settlement_data["ytd_commission"],
            "ytd_payout": settlement_data["ytd_payout"],
        },
    )


@login_required
def producer_order_notifications(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    pending_orders_count = ProducerOrder.objects.filter(
        producer=request.user,
        status=ProducerOrder.Status.PENDING,
    ).count()
    producer_products = Product.objects.filter(producer=request.user).only(
        "stock",
        "stock_warning_level",
    )
    low_stock_count = sum(1 for product in producer_products if product.is_low_stock)
    return JsonResponse(
        {
            "pending_orders_count": pending_orders_count,
            "low_stock_count": low_stock_count,
        }
    )


@login_required
def producer_settlements(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    settlement_data = _producer_settlement_data(request.user)

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="producer-settlement-report.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Settlement Period",
                "Order Number",
                "Customer",
                "Products",
                "Order Date",
                "Gross Amount",
                "Commission (5%)",
                "Producer Payout (95%)",
                "Payment Status",
            ]
        )
        for row in settlement_data["rows"]:
            writer.writerow(
                [
                    f"{row['period_start']} to {row['period_end']}",
                    row["order_id"],
                    row["customer_label"],
                    row["items_csv"],
                    row["order_date"],
                    row["gross_amount"],
                    row["commission_amount"],
                    row["payout_amount"],
                    row["payment_status"],
                ]
            )
        return response

    return render(
        request,
        "dashboards/producer_settlements.html",
        {
            "producer_profile": getattr(request.user, "producer_profile", None),
            "settlement_rows": settlement_data["rows"],
            "period_summaries": settlement_data["period_summaries"],
            "latest_settlement": settlement_data["latest_summary"],
            "ytd_gross": settlement_data["ytd_gross"],
            "ytd_commission": settlement_data["ytd_commission"],
            "ytd_payout": settlement_data["ytd_payout"],
        },
    )


@login_required
def producer_stock(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    low_stock_only = request.GET.get("low_stock") == "1"

    products_qs = (
        Product.objects.filter(producer=request.user)
        .select_related("category")
        .order_by("name")
    )
    products_all = list(products_qs)
    products = [product for product in products_all if product.is_low_stock] if low_stock_only else products_all
    return render(
        request,
        "dashboards/stock.html",
        {
            "products": products,
            "products_count": len(products_all),
            "low_stock_count": len([p for p in products_all if p.is_low_stock]),
            "low_stock_only": low_stock_only,
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
        form = ProducerProductForm(request.POST, request.FILES, user=request.user)

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
        form = ProducerProductForm(request.POST, request.FILES, instance=product, user=request.user)
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
    try:
        product.delete()
        messages.success(request, f"{product_name} was deleted.")
    except ProtectedError:
        product.availability_status = Product.AvailabilityStatus.UNAVAILABLE
        product.is_active = False
        product.save(update_fields=["availability_status", "is_active", "updated_at"])
        messages.info(
            request,
            f"{product_name} has existing order history, so it was archived and hidden instead of being deleted.",
        )
    return redirect("producer_stock")


@login_required
def add_stock(request, product_id):
    return redirect("edit_product", product_id=product_id)
