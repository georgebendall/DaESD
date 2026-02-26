from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, CustomerProfile, ProducerProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Shows our custom fields in Django Admin.

    We reuse Django's standard UserAdmin and just add role + email.
    """

    # What columns you see on the user list page
    list_display = ("username", "email", "role", "is_staff", "is_active")

    # Filters on the right side
    list_filter = ("role", "is_staff", "is_active")

    # Search box targets
    search_fields = ("username", "email")

    # Add role to the admin edit form
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "postcode", "phone", "created_at")
    search_fields = ("user__username", "user__email", "postcode")


@admin.register(ProducerProfile)
class ProducerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "business_name", "postcode", "is_approved", "created_at")
    search_fields = ("user__username", "user__email", "business_name", "postcode")
    list_filter = ("is_approved",)
