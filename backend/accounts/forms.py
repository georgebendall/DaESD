from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(forms.Form):
    ROLE_CHOICES = [
        (User.Role.CUSTOMER, "Customer"),
        (User.Role.PRODUCER, "Producer"),
    ]

    role = forms.ChoiceField(choices=ROLE_CHOICES)

    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    # Customer fields
    phone = forms.CharField(max_length=30, required=False)
    customer_postcode = forms.CharField(max_length=12, required=False)
    terms = forms.BooleanField(required=False)

    # Producer fields
    business_name = forms.CharField(max_length=120, required=False)
    contact_phone = forms.CharField(max_length=30, required=False)
    address_line1 = forms.CharField(max_length=120, required=False)
    city = forms.CharField(max_length=80, required=False)
    producer_postcode = forms.CharField(max_length=12, required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")

        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        else:
            validate_password(p1)

        # Role-based required fields
        if role == User.Role.CUSTOMER:
            if not cleaned.get("terms"):
                self.add_error("terms", "You must accept the terms & conditions.")

        if role == User.Role.PRODUCER:
            if not cleaned.get("business_name"):
                self.add_error("business_name", "Business name is required.")
            if not cleaned.get("producer_postcode"):
                self.add_error("producer_postcode", "Postcode is required.")

        return cleaned