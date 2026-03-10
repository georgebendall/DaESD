from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import RegisterForm
from .models import User, CustomerProfile, ProducerProfile
@login_required
def after_login(request):
    user = request.user
    role = getattr(user, "role", "")

    # Admins -> custom admin dashboard
    if user.is_staff or role == "admin":
        return redirect("/admin-dashboard/")

    # Producers -> stock page (if you don't have it yet, send to store)
    if role == "producer":
        return redirect("/shop/products/")

    # Customers -> store
    return redirect("/shop/products/")

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data["role"]

            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                role=role,
            )

            if role == User.Role.CUSTOMER:
                CustomerProfile.objects.create(
                    user=user,
                    phone=form.cleaned_data.get("phone", ""),
                    postcode=form.cleaned_data.get("customer_postcode", ""),
                )

            if role == User.Role.PRODUCER:
                ProducerProfile.objects.create(
                    user=user,
                    business_name=form.cleaned_data["business_name"],
                    contact_phone=form.cleaned_data.get("contact_phone", ""),
                    address_line1=form.cleaned_data.get("address_line1", ""),
                    city=form.cleaned_data.get("city", ""),
                    postcode=form.cleaned_data.get("producer_postcode", ""),
                    is_approved=True,
                )

            login(request, user)
            return redirect("/shop/products/")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})