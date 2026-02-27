from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import Product, Category


def product_list_page(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()

    qs = Product.objects.filter(is_active=True)

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    # newest first
    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    categories = Category.objects.order_by("name")

    return render(
        request,
        "catalog/product_list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "category_slug": category_slug,
            "categories": categories,
        },
    )

