from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CustomerRegistrationForm, ProducerRegistrationForm
from .models import CustomerProfile, ProducerProfile, User


@login_required
def after_login(request):
    user = request.user
    role = getattr(user, "role", "")  # Ensure role is uppercase for comparison
    print(f"DEBUG: User {user.username} has role: '{role}'") # Check your terminal output
    if user.is_staff or role == User.Role.ADMIN:
        return redirect("admin_dashboard")

    # UPDATE THIS SECTION:
    if role == User.Role.PRODUCER:
        return redirect("producer_dashboard") # Matches the name in dashboards/urls.py

    if role == User.Role.CUSTOMER:
        return redirect("customer_dashboard")

    return redirect("home")


def register_choice(request):
    if request.user.is_authenticated:
        return redirect("product_list")
    return render(request, "registration/register_choice.html")


def register_customer(request):
    if request.user.is_authenticated:
        return redirect("product_list")

    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.role = User.Role.CUSTOMER
            user.save()

            CustomerProfile.objects.create(
                user=user,
                phone=form.cleaned_data["phone"],
                postcode=form.cleaned_data["postcode"],
            )

            login(request, user)
            messages.success(request, "Customer account created successfully.")
            return redirect("home") # Ensure this name exists in urls.py
    else:
        form = CustomerRegistrationForm()

    return render(request, "registration/register_customer.html", {"form": form})


def register_producer(request):
    if request.user.is_authenticated:
        return redirect("product_list")

    if request.method == "POST":
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.role = User.Role.PRODUCER
            user.save()

            ProducerProfile.objects.create(
                user=user,
                business_name=form.cleaned_data["business_name"],
                contact_phone=form.cleaned_data["contact_phone"],
                address_line1=form.cleaned_data["address_line1"],
                city=form.cleaned_data["city"],
                postcode=form.cleaned_data["postcode"],
                is_approved=True,
            )

            login(request, user)
            messages.success(request, "Producer account created successfully.")
            return redirect("producer_dashboard") # Ensure this name exists in urls.py
    else:
        form = ProducerRegistrationForm()

    return render(request, "registration/register_producer.html", {"form": form})