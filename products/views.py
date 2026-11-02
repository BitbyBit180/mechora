import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.roles import get_user_role

from .models import Product


def _is_admin(request):
    return request.user.is_authenticated and (
        request.user.is_superuser or get_user_role(request.user) == "Admin"
    )


def _record(product):
    return {
        "id": product.pk,
        "product_code": product.product_code,
        "name": product.name,
        "description": product.description,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@require_http_methods(["GET", "POST"])
def product_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if request.method == "GET":
        products = Product.objects.all()
        if get_user_role(request.user) != "Admin" and not request.user.is_superuser:
            products = products.filter(is_active=True)
        return JsonResponse({"products": [_record(product) for product in products]})
    if not _is_admin(request):
        return JsonResponse({"detail": "Administrator role required."}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "Request body must be valid JSON."}, status=400)
    code = str(payload.get("product_code", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not code or not name:
        return JsonResponse({"detail": "product_code and name are required."}, status=400)
    if Product.objects.filter(product_code=code).exists():
        return JsonResponse({"detail": "A product with this code already exists."}, status=409)
    product = Product.objects.create(
        product_code=code,
        name=name,
        description=str(payload.get("description", "")).strip(),
        is_active=bool(payload.get("is_active", True)),
    )
    return JsonResponse(_record(product), status=201)


@require_http_methods(["GET", "PATCH"])
def product_detail(request, product_id):
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"detail": "Product not found."}, status=404)
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if request.method == "GET":
        if not product.is_active and not _is_admin(request):
            return JsonResponse({"detail": "Product not found."}, status=404)
        return JsonResponse(_record(product))
    if not _is_admin(request):
        return JsonResponse({"detail": "Administrator role required."}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "Request body must be valid JSON."}, status=400)
    for field in ("name", "description", "is_active"):
        if field in payload:
            setattr(product, field, payload[field])
    product.save()
    return JsonResponse(_record(product))
