from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from catalog.models import Product, ProductInventoryHistory
from orders.models import Order
from .forms import ProducerProductForm


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return render(request, "dashboards/forbidden.html", status=403)
    return render(request, "dashboards/admin_dashboard.html")


@login_required
def customer_dashboard(request):
    if getattr(request.user, "role", "") != "customer":
        return redirect("/accounts/after-login/")

    user = request.user
    products_count = Product.objects.filter(is_active=True).count()
    my_orders_qs = Order.objects.filter(customer=user).order_by("-created_at")
    my_orders_count = my_orders_qs.count()
    recent_orders = my_orders_qs[:5]

    cart_items = 0
    try:
        from orders.models import Cart, CartItem
        cart = Cart.objects.filter(customer=user).first()
        cart_items = CartItem.objects.filter(cart=cart).count() if cart else 0
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

    context = {
        "products_count": products_qs.count(),
        "active_products_count": products_qs.filter(is_active=True).count(),
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products[:5],
        "recent_products": products_qs[:5],
    }
    return render(request, "dashboards/producer_dashboard.html", context)


@login_required
def producer_stock(request):
    redirect_response = _producer_only_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = (
        Product.objects.filter(producer=request.user)
        .select_related("category")
        .prefetch_related("allergens")
        .order_by("name")
    )

    return render(request, "dashboards/stock.html", {"products": products})


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
        if form.is_valid():
            product = form.save()

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
        if form.is_valid():
            updated_product = form.save()

            if old_stock != updated_product.stock or old_availability != updated_product.availability_status:
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