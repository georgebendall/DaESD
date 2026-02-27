from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from payments.models import PaymentTransaction

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
