from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from orders.models import Order, OrderItem, ProducerOrder
from reviews.forms import ReviewForm
from reviews.models import Review

from .models import Allergen, Category, Product, calculate_food_miles


MAX_FOOD_MILES_OPTIONS = [
    ("", "Any distance"),
    ("5", "Within 5 miles"),
    ("10", "Within 10 miles"),
    ("25", "Within 25 miles"),
    ("50", "Within 50 miles"),
]

SORT_OPTIONS = [
    ("", "Name A-Z"),
    ("nearest", "Nearest first"),
]


def _saved_customer_postcode(request):
    if not request.user.is_authenticated or getattr(request.user, "role", "") != "customer":
        return ""
    return getattr(getattr(request.user, "customer_profile", None), "postcode", "").strip()


def _product_food_miles(product, postcode):
    producer_postcode = getattr(getattr(product.producer, "producer_profile", None), "postcode", "")
    if not postcode or not producer_postcode:
        return None
    return calculate_food_miles(postcode, producer_postcode)


def product_list(request):
    return product_list_page(request)


def surplus_deals_page(request):
    if request.GET.copy().get("surplus") != "1":
        mutable_get = request.GET.copy()
        mutable_get["surplus"] = "1"
        request.GET = mutable_get
    return product_list_page(request)


def product_list_page(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    allergen_id = (request.GET.get("allergen") or "").strip()
    exclude_allergen_id = (request.GET.get("exclude_allergen") or "").strip()
    availability = (request.GET.get("availability") or "").strip()
    organic_only = (request.GET.get("organic") or "").strip()
    surplus_only = (request.GET.get("surplus") or "").strip()
    max_food_miles = (request.GET.get("max_food_miles") or "").strip()
    sort_by = (request.GET.get("sort") or "").strip()
    entered_postcode = (request.GET.get("postcode") or "").strip()
    customer_postcode_missing = False
    food_miles_notice = ""
    unresolved_food_miles_count = 0

    saved_postcode = _saved_customer_postcode(request)
    filter_postcode = saved_postcode or entered_postcode
    show_postcode_filter = not bool(saved_postcode)

    qs = (
        Product.objects.filter(is_active=True)
        .select_related("category", "producer", "producer__producer_profile")
        .prefetch_related("allergens")
    )

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(producer__username__icontains=q)
            | Q(producer__producer_profile__business_name__icontains=q)
            | Q(allergens__name__icontains=q)
        )

    if allergen_id.isdigit():
        qs = qs.filter(allergens__id=allergen_id)

    if exclude_allergen_id.isdigit():
        qs = qs.exclude(allergens__id=exclude_allergen_id)

    valid_availability_values = {value for value, _ in Product.AvailabilityStatus.choices}
    if availability in valid_availability_values:
        qs = qs.filter(availability_status=availability)

    if organic_only == "1":
        qs = qs.filter(is_organic=True)

    if surplus_only == "1":
        qs = qs.filter(
            is_surplus=True,
            surplus_discount_percent__gt=0,
            surplus_expires_at__gt=timezone.now(),
        )

    products = list(qs.distinct())

    should_compute_food_miles = bool(filter_postcode) or (
        request.user.is_authenticated and getattr(request.user, "role", "") == "customer"
    )

    if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
        customer_postcode_missing = not saved_postcode

    if should_compute_food_miles:
        for product in products:
            if saved_postcode and request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
                product.food_miles = product.food_miles_for_customer(request.user)
            else:
                product.food_miles = _product_food_miles(product, filter_postcode)
    else:
        for product in products:
            product.food_miles = None

    max_food_miles_value = int(max_food_miles) if max_food_miles.isdigit() else None
    requested_food_miles_filter = bool(max_food_miles_value) or sort_by == "nearest"

    if requested_food_miles_filter and not filter_postcode:
        food_miles_notice = "Enter your postcode to filter or sort by food miles."
    else:
        if max_food_miles_value:
            filtered_products = []
            for product in products:
                if product.food_miles is None:
                    unresolved_food_miles_count += 1
                    continue
                if product.food_miles <= max_food_miles_value:
                    filtered_products.append(product)
            products = filtered_products

            if unresolved_food_miles_count:
                food_miles_notice = "Some products were hidden because food miles were unavailable."

        if sort_by == "nearest":
            products.sort(
                key=lambda product: (
                    product.food_miles is None,
                    product.food_miles if product.food_miles is not None else float("inf"),
                    product.name.lower(),
                )
            )
        else:
            products.sort(key=lambda product: product.name.lower())

    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

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
            "excluded_allergen": exclude_allergen_id,
            "availability": availability,
            "availability_choices": Product.AvailabilityStatus.choices,
            "organic_only": organic_only,
            "surplus_only": surplus_only,
            "max_food_miles": max_food_miles,
            "max_food_miles_options": MAX_FOOD_MILES_OPTIONS,
            "sort_by": sort_by,
            "sort_options": SORT_OPTIONS,
            "filter_postcode": filter_postcode,
            "entered_postcode": entered_postcode,
            "show_postcode_filter": show_postcode_filter,
            "customer_postcode_missing": customer_postcode_missing,
            "food_miles_notice": food_miles_notice,
        },
    )


def product_detail_page(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("category", "producer"),
        id=product_id,
        is_active=True,
    )

    food_miles = None
    customer_postcode_missing = False
    can_review = False
    existing_review = None
    review_form = None
    average_rating = None

    review_qs = product.reviews.select_related("reviewer")
    review_count = review_qs.count()
    if review_count:
        average_rating = round(
            sum(review.rating for review in review_qs) / review_count,
            1,
        )

    if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
        customer_postcode_missing = not getattr(
            getattr(request.user, "customer_profile", None),
            "postcode",
            "",
        ).strip()
        food_miles = product.food_miles_for_customer(request.user)
        existing_review = Review.objects.filter(product=product, reviewer=request.user).first()
        has_completed_purchase = OrderItem.objects.filter(
            order__customer=request.user,
            order__status__in=[Order.Status.PAID, Order.Status.COMPLETED],
            order__producer_orders__producer=product.producer,
            order__producer_orders__status__in=[
                ProducerOrder.Status.ACCEPTED,
                ProducerOrder.Status.DISPATCHED,
                ProducerOrder.Status.COMPLETED,
            ],
            product=product,
        ).exists()
        can_review = has_completed_purchase and existing_review is None
        if can_review:
            review_form = ReviewForm()

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "food_miles": food_miles,
            "customer_postcode_missing": customer_postcode_missing,
            "can_review": can_review,
            "existing_review": existing_review,
            "review_form": review_form,
            "average_rating": average_rating,
            "review_count": review_count,
        },
    )
