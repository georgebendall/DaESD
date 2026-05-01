from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import CustomerProfile, User


class BaseRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

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

    def _apply_bootstrap_classes(self):
        for _, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})


class CustomerRegistrationForm(BaseRegistrationForm):
    account_type = forms.ChoiceField(choices=CustomerProfile.AccountType.choices)
    phone = forms.CharField(max_length=30, required=False)
    postcode = forms.CharField(max_length=12, required=True)
    organisation_name = forms.CharField(max_length=160, required=False)
    institutional_email = forms.EmailField(required=False)
    address_line1 = forms.CharField(max_length=120, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "account_type",
            "organisation_name",
            "institutional_email",
            "phone",
            "address_line1",
            "postcode",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get("account_type")
        organisation_name = (cleaned_data.get("organisation_name") or "").strip()

        if account_type in {
            CustomerProfile.AccountType.COMMUNITY_GROUP,
            CustomerProfile.AccountType.RESTAURANT,
        } and not organisation_name:
            self.add_error("organisation_name", "Organisation name is required for this account type.")

        return cleaned_data


class ProducerRegistrationForm(BaseRegistrationForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()


class RememberMeAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        self.fields["password"].widget.attrs.update({"class": "form-control"})
        self.fields["remember_me"].widget.attrs.update({"class": "form-check-input"})
