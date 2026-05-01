from django import forms
from django.utils.text import slugify

from catalog.models import Allergen, Category, Product


def _build_unique_slug(user, name, instance_pk=None):
    base = slugify(name) or "product"
    slug = base
    counter = 2

    qs = Product.objects.filter(producer=user)
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)

    while qs.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1

    return slug


class ProducerProductForm(forms.ModelForm):
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 6}),
    )
    surplus_expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"}
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    best_before_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}
        ),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "description",
            "unit",
            "price",
            "stock",
            "availability_status",
            "stock_warning_level",
            "allergens",
            "is_surplus",
            "surplus_discount_percent",
            "surplus_expires_at",
            "surplus_note",
            "best_before_date",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "unit": forms.Select(attrs={"class": "form-select"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "availability_status": forms.Select(attrs={"class": "form-select"}),
            "stock_warning_level": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "is_surplus": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "surplus_discount_percent": forms.NumberInput(attrs={"class": "form-control", "min": "10", "max": "50"}),
            "surplus_note": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # ✅ Populate dropdowns
        self.fields["category"].queryset = Category.objects.order_by("name")
        self.fields["allergens"].queryset = Allergen.objects.order_by("name")

        # ✅ CRITICAL: set producer BEFORE validation happens
        # so Product.clean() doesn't crash
        if self.user and not self.instance.pk:
            self.instance.producer = self.user

        if self.instance.pk and self.instance.surplus_expires_at:
            self.initial["surplus_expires_at"] = self.instance.surplus_expires_at.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        is_surplus = cleaned_data.get("is_surplus")
        discount = cleaned_data.get("surplus_discount_percent") or 0
        expires_at = cleaned_data.get("surplus_expires_at")

        if is_surplus:
            if discount < 10 or discount > 50:
                self.add_error("surplus_discount_percent", "Surplus discount must be between 10 and 50.")
            if not expires_at:
                self.add_error("surplus_expires_at", "Please add an expiry date for the surplus deal.")

        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)

        # ✅ Always enforce producer from logged-in user
        if self.user:
            product.producer = self.user
            product.slug = _build_unique_slug(
                self.user,
                product.name,
                product.pk,
            )

        if commit:
            product.save()
            self.save_m2m()

        return product
