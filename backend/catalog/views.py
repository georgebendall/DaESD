from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Allergen, Category, Product


def product_list(request):
    return product_list_page(request)


def product_list_page(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    allergen_id = (request.GET.get("allergen") or "").strip()
    organic_only = (request.GET.get("organic") or "").strip()

    qs = Product.objects.filter(is_active=True).select_related("category", "producer")

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(producer__username__icontains=q)
            | Q(producer__producer_profile__business_name__icontains=q)
        )

    if allergen_id:
        qs = qs.filter(allergens__id=allergen_id)

    if organic_only == "1":
        qs = qs.filter(is_organic=True)

    qs = qs.distinct().order_by("name")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
        for product in page_obj.object_list:
            product.food_miles = product.food_miles_for_customer(request.user)

    categories = Category.objects.order_by("name")
    allergens = Allergen.objects.order_by("name")

    request.session["last_product_list_url"] = request.get_full_path()

    return render(
        request,
        "catalog/product_list.html",
        {
            "page_obj": page_obj,
            "products": page_obj.object_list,
            "q": q,
            "category_slug": category_slug,
            "categories": categories,
            "allergens": allergens,
            "selected_allergen": allergen_id,
            "organic_only": organic_only,
        },
    )


def product_detail_page(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("category", "producer"),
        id=product_id,
        is_active=True,
    )

    food_miles = None
    if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
        food_miles = product.food_miles_for_customer(request.user)

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "food_miles": food_miles,
        },
    )