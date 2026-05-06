from django.contrib import admin
from .models import RecurringOrder, RecurringOrderItem

admin.site.register(RecurringOrder)
admin.site.register(RecurringOrderItem)
