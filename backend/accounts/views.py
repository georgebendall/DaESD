import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import (
    CustomerRegistrationForm,
    ProducerRegistrationForm,
    RememberMeAuthenticationForm,
)
from .models import CustomerProfile, ProducerProfile, User


logger = logging.getLogger(__name__)


class BrfnLoginView(LoginView):
    authentication_form = RememberMeAuthenticationForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    lockout_attempt_limit = 5
    lockout_window = timedelta(minutes=10)

    def _lockout_remaining_seconds(self):
        lockout_until = self.request.session.get("login_lockout_until")
        if not lockout_until:
            return 0

        remaining = int(lockout_until - timezone.now().timestamp())
        return max(remaining, 0)

    def dispatch(self, request, *args, **kwargs):
        if self._lockout_remaining_seconds() > 0 and request.method.lower() == "post":
            logger.warning("Blocked login attempt during lockout for username=%s", request.POST.get("username", ""))
            form = self.get_form()
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    login_blocked=True,
                    lockout_minutes=max(1, self._lockout_remaining_seconds() // 60),
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.request.session.pop("login_failed_attempts", None)
        self.request.session.pop("login_lockout_until", None)

        response = super().form_valid(form)
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(60 * 60 * 24 * 14)
        else:
            self.request.session.set_expiry(0)

        logger.info("Successful login for username=%s", form.get_user().username)
        return response

    def form_invalid(self, form):
        attempts = int(self.request.session.get("login_failed_attempts", 0)) + 1
        self.request.session["login_failed_attempts"] = attempts

        if attempts >= self.lockout_attempt_limit:
            self.request.session["login_lockout_until"] = (
                timezone.now() + self.lockout_window
            ).timestamp()
            logger.warning(
                "Too many failed login attempts for username=%s",
                self.request.POST.get("username", ""),
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    login_blocked=True,
                    lockout_minutes=int(self.lockout_window.total_seconds() // 60),
                )
            )

        logger.warning(
            "Failed login attempt %s for username=%s",
            attempts,
            self.request.POST.get("username", ""),
        )
        return super().form_invalid(form)


class BrfnLogoutView(LogoutView):
    next_page = "login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logger.info("Logout for username=%s", request.user.username)
        return super().dispatch(request, *args, **kwargs)


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
                account_type=form.cleaned_data.get("account_type"),
                organisation_name=form.cleaned_data.get("organisation_name", ""),
                institutional_email=form.cleaned_data.get("institutional_email", ""),
                phone=form.cleaned_data.get("phone", ""),
                address_line1=form.cleaned_data.get("address_line1", ""),
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
