from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def admin_dashboard(request):
    # This is YOUR admin page (your software).
    # It is NOT Django admin.

    # Simple rule: only staff can view (later you can use roles).
    if not request.user.is_staff:
        return HttpResponse("Forbidden: admins only.", status=403)

    return HttpResponse("Custom Admin Dashboard. Later: commission reports, settlements, etc.")