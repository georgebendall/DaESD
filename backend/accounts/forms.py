from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import User


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=30, required=False)
    postcode = forms.CharField(max_length=12, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone", "postcode", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password)
        return password


class ProducerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    business_name = forms.CharField(max_length=120, required=True)
    contact_phone = forms.CharField(max_length=30, required=False)
    address_line1 = forms.CharField(max_length=120, required=False)
    city = forms.CharField(max_length=80, required=False)
    postcode = forms.CharField(max_length=12, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "business_name",
            "contact_phone",
            "address_line1",
            "city",
            "postcode",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password)
        return password