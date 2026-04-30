from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CustomerRegistrationForm, ProducerRegistrationForm
from .models import CustomerProfile, ProducerProfile, User


@login_required
def after_login(request):
    user = request.user

    if user.is_admin_user:
        return redirect("admin_dashboard")

    if user.is_producer_user:
        return redirect("producer_dashboard")

    if user.is_customer_user:
        return redirect("customer_dashboard")

    return redirect("home")


def register_choice(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "registration/register_choice.html")


def register_customer(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.role = User.Role.CUSTOMER
            user.is_staff = False
            user.is_superuser = False
            user.save()

            CustomerProfile.objects.create(
                user=user,
                phone=form.cleaned_data.get("phone", ""),
                postcode=form.cleaned_data.get("postcode", ""),
            )

            login(request, user)
            messages.success(request, "Customer account created successfully.")
            return redirect("customer_dashboard")
    else:
        form = CustomerRegistrationForm()

    return render(request, "registration/register_customer.html", {"form": form})


def register_producer(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.role = User.Role.PRODUCER
            user.is_staff = False
            user.is_superuser = False
            user.save()

            ProducerProfile.objects.create(
                user=user,
                business_name=form.cleaned_data["business_name"],
                contact_phone=form.cleaned_data.get("contact_phone", ""),
                address_line1=form.cleaned_data.get("address_line1", ""),
                city=form.cleaned_data.get("city", ""),
                postcode=form.cleaned_data.get("postcode", ""),
                is_approved=True,
            )

            login(request, user)
            messages.success(request, "Producer account created successfully.")
            return redirect("producer_dashboard")
    else:
        form = ProducerRegistrationForm()

    return render(request, "registration/register_producer.html", {"form": form})
