from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "rating": forms.Select(
                choices=[(5, "5 - Excellent"), (4, "4 - Good"), (3, "3 - Average"), (2, "2 - Poor"), (1, "1 - Very poor")],
                attrs={"class": "form-select"},
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Share a short, honest review of this product.",
                }
            ),
        }

