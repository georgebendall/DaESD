from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from catalog.models import Product
from orders.models import Order, OrderItem, ProducerOrder

from .forms import ReviewForm
from .models import Review


@login_required
def create_review(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if getattr(request.user, "role", "") != "customer":
        messages.error(request, "Only customers can leave product reviews.")
        return redirect("product_detail", product_id=product.id)

    has_purchased = OrderItem.objects.filter(
        order__customer=request.user,
        order__status__in=[Order.Status.PAID, Order.Status.COMPLETED],
        order__producer_orders__producer=product.producer,
        order__producer_orders__status__in=[
            ProducerOrder.Status.ACCEPTED,
            ProducerOrder.Status.DISPATCHED,
            ProducerOrder.Status.COMPLETED,
        ],
        product=product,
    ).exists()
    if not has_purchased:
        messages.error(request, "You can review a product after payment once the producer has accepted the order.")
        return redirect("product_detail", product_id=product.id)

    if Review.objects.filter(product=product, reviewer=request.user).exists():
        messages.info(request, "You have already reviewed this product.")
        return redirect("product_detail", product_id=product.id)

    if request.method != "POST":
        return redirect("product_detail", product_id=product.id)

    form = ReviewForm(request.POST)
    form.instance.product = product
    form.instance.reviewer = request.user
    if form.is_valid():
        form.save()
        messages.success(request, "Thanks for leaving a review.")
    else:
        messages.error(request, "Please complete the review form correctly.")

    return redirect("product_detail", product_id=product.id)
