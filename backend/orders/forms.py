from django import forms

from .models import RecurringOrder


class RecurringOrderForm(forms.ModelForm):
    class Meta:
        model = RecurringOrder
        fields = ["name", "recurrence", "order_day", "delivery_day"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "recurrence": forms.Select(attrs={"class": "form-select"}),
            "order_day": forms.Select(
                choices=[
                    ("monday", "Monday"),
                    ("tuesday", "Tuesday"),
                    ("wednesday", "Wednesday"),
                    ("thursday", "Thursday"),
                    ("friday", "Friday"),
                    ("saturday", "Saturday"),
                    ("sunday", "Sunday"),
                ],
                attrs={"class": "form-select"},
            ),
            "delivery_day": forms.Select(
                choices=[
                    ("monday", "Monday"),
                    ("tuesday", "Tuesday"),
                    ("wednesday", "Wednesday"),
                    ("thursday", "Thursday"),
                    ("friday", "Friday"),
                    ("saturday", "Saturday"),
                    ("sunday", "Sunday"),
                ],
                attrs={"class": "form-select"},
            ),
        }
