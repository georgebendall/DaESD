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

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "description",
            "price",
            "stock",
            "availability_status",
            "stock_warning_level",
            "allergens",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "availability_status": forms.Select(attrs={"class": "form-select"}),
            "stock_warning_level": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
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