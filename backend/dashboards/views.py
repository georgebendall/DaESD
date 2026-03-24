from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect

from accounts.models import User
from catalog.models import Product
from orders.models import Order

@login_required
def admin_dashboard(request):
    # Only admins/staff can view
    if not request.user.is_staff:
        return render(request, "dashboards/forbidden.html", status=403)

    # This MUST render a template (not HttpResponse) so it looks like a page
    return render(request, "dashboards/admin_dashboard.html")

@login_required
def customer_dashboard(request):
    # Only customers
    if getattr(request.user, "role", "") != "customer":
        return redirect("/accounts/after-login/")

    user = request.user

    # Basic KPIs
    products_count = Product.objects.filter(is_active=True).count()
    my_orders_qs = Order.objects.filter(customer=user).order_by("-created_at")
    my_orders_count = my_orders_qs.count()
    recent_orders = my_orders_qs[:5]

    # Cart count (you already have cart_item_count context processor for navbar,
    # but we can also fetch it here if Cart exists)
    cart_items = None
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

#PRODUCER END----------------------------------------------------------------------------------
@login_required
def producer_dashboard(request):
    # Get the role and force it to uppercase for a safe comparison
    user_role = getattr(request.user, 'role', '').upper()

    if not request.user.is_authenticated or user_role != 'PRODUCER':
        # This is where the 302 redirect to home is happening!
        return redirect('home') 
        
    return render(request, "dashboards/producer_dashboard.html")

# dashboards/views.py

def producer_stock(request):
    # Security: Redirect if not a producer
    if getattr(request.user, 'role', '').upper() != 'PRODUCER':
        return redirect('home')
        
    return render(request, "dashboards/stock.html")

def edit_stock_list(request):
    # This view would show the list of products specifically for editing their batches
    products = Product.objects.filter(producer=request.user) # or your specific logic
    return render(request, "dashboards/editstock.html", {"products": products})
# dashboards/views.py

def add_product(request):
    # Temporary placeholder
    return render(request, "dashboards/add_product.html")

def edit_product(request, product_id):
    # Temporary placeholder
    return render(request, "dashboards/edit_product.html")

def delete_product(request, product_id):
    # Temporary placeholder - usually redirects back to stock after deleting
    return redirect("producer_stock")
# dashboards/views.py

def add_stock(request, product_id):
    # This is a placeholder until you build the actual stock entry form
    return render(request, "dashboards/add_stock_form.html", {"product_id": product_id})