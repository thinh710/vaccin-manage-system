from datetime import timedelta

from django.db import models, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from feature.authentication.models import User
from feature.csrf import csrf_protect_session_api
from rest_framework import serializers as drf_serializers

from .models import (
    Supplier,
    StorageLocation,
    Vaccine,
    StockImport,
    StockExport,
    StockAdjustment,
)
from .permissions import CanReadVaccineStock, IsAdminOrReadOnly
from .serializers import (
    SupplierSerializer,
    StorageLocationSerializer,
    VaccineSerializer,
    StockImportSerializer,
    StockExportSerializer,
    StockAdjustmentSerializer,
)


def _flatten_serializer_errors(serializer):
    return " ".join(str(message) for messages in serializer.errors.values() for message in messages)


def _apply_inventory_filters(request, vaccines, today):
    keyword = request.GET.get("q", "").strip().lower()
    supplier_value = request.GET.get("supplier", "").strip().lower()
    location_value = request.GET.get("location", "").strip().lower()
    status_value = request.GET.get("status", "").strip().lower()

    filtered = []
    for vaccine in vaccines:
        vaccine_status = "normal"
        if vaccine.expiration_date < today:
            vaccine_status = "expired"
        elif vaccine.quantity <= vaccine.minimum_stock:
            vaccine_status = "low"
        elif today <= vaccine.expiration_date <= today + timedelta(days=30):
            vaccine_status = "expiring"

        search_blob = " ".join(
            [
                vaccine.name.lower(),
                vaccine.batch_number.lower(),
                vaccine.manufacturer.lower(),
                (vaccine.supplier.name.lower() if vaccine.supplier else ""),
                (vaccine.location.name.lower() if vaccine.location else ""),
            ]
        )

        if keyword and keyword not in search_blob:
            continue
        if supplier_value and (not vaccine.supplier or vaccine.supplier.name.lower() != supplier_value):
            continue
        if location_value and (not vaccine.location or vaccine.location.name.lower() != location_value):
            continue
        if status_value and vaccine_status != status_value:
            continue
        filtered.append(vaccine)

    return filtered


def _get_session_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None, redirect("/auth/login-page/")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None, redirect("/auth/login-page/")

    return user, None


def _can_manage_inventory(user):
    """Chỉ Admin mới có quyền truy cập module quản lý kho."""
    return user.role == User.ROLE_ADMIN


def _adjust_vaccine_stock(vaccine_id, delta):
    vaccine = Vaccine.objects.select_for_update().get(pk=vaccine_id)
    next_quantity = vaccine.quantity + delta
    if next_quantity < 0:
        raise drf_serializers.ValidationError(
            {
                "detail": (
                    f"Tồn kho không đủ để cập nhật phiếu. Hiện có: {vaccine.quantity}, "
                    f"thay đổi: {delta}."
                )
            }
        )
    vaccine.quantity = next_quantity
    vaccine.save(update_fields=["quantity"])


def _apply_stock_import(stock_import, direction=1):
    _adjust_vaccine_stock(stock_import.vaccine_id, stock_import.quantity * direction)


def _apply_stock_export(stock_export, direction=1):
    _adjust_vaccine_stock(stock_export.vaccine_id, -stock_export.quantity * direction)


def _stock_adjustment_delta(adjustment):
    return adjustment.quantity if adjustment.adjustment_type == "increase" else -adjustment.quantity


def _apply_stock_adjustment(adjustment, direction=1):
    _adjust_vaccine_stock(adjustment.vaccine_id, _stock_adjustment_delta(adjustment) * direction)


class CsrfProtectedModelViewSet(viewsets.ModelViewSet):
    def dispatch(self, request, *args, **kwargs):
        protected_dispatch = csrf_protect_session_api(super().dispatch)
        return protected_dispatch(request, *args, **kwargs)


@ensure_csrf_cookie
def inventory_dashboard_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    today = timezone.localdate()
    vaccines = list(
        Vaccine.objects.select_related("supplier", "location")
        .all()
        .order_by("expiration_date", "-created_at")
    )
    suppliers = list(Supplier.objects.all().order_by("name"))
    locations = list(StorageLocation.objects.all().order_by("name"))

    total_vaccines = len(vaccines)
    total_stock = sum(vaccine.quantity for vaccine in vaccines)
    low_stock_count = sum(1 for vaccine in vaccines if vaccine.quantity <= vaccine.minimum_stock)
    expired_count = sum(1 for vaccine in vaccines if vaccine.expiration_date < today)
    near_expiry_count = sum(
        1
        for vaccine in vaccines
        if today <= vaccine.expiration_date <= today + timedelta(days=30)
    )

    recent_imports = list(
        StockImport.objects.select_related("vaccine", "supplier")
        .all()
        .order_by("-created_at")[:5]
    )
    recent_exports = list(
        StockExport.objects.select_related("vaccine")
        .all()
        .order_by("-created_at")[:5]
    )
    recent_adjustments = list(
        StockAdjustment.objects.select_related("vaccine")
        .all()
        .order_by("-created_at")[:5]
    )

    recent_transactions = sorted(
        [
            {
                "type": "import",
                "label": "Nhập kho",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.supplier.name if item.supplier else "Không rõ nhà cung cấp",
                "created_at": item.created_at,
            }
            for item in recent_imports
        ]
        + [
            {
                "type": "export",
                "label": "Xuất kho",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.destination,
                "created_at": item.created_at,
            }
            for item in recent_exports
        ]
        + [
            {
                "type": "adjustment",
                "label": "Điều chỉnh",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.reason,
                "created_at": item.created_at,
            }
            for item in recent_adjustments
        ],
        key=lambda entry: entry["created_at"],
        reverse=True,
    )[:8]

    context = {
        "user": user,
        "today": today,
        "summary": {
            "total_vaccines": total_vaccines,
            "total_stock": total_stock,
            "low_stock_count": low_stock_count,
            "expired_count": expired_count,
            "near_expiry_count": near_expiry_count,
        },
        "vaccines": vaccines,
        "suppliers": suppliers,
        "locations": locations,
        "recent_transactions": recent_transactions,
    }
    return render(request, "assets/dashboard.html", context)


@ensure_csrf_cookie
def inventory_overview_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    today = timezone.localdate()
    vaccines = list(Vaccine.objects.all())

    context = {
        "user": user,
        "today": today,
        "summary": {
            "total_vaccines": len(vaccines),
            "total_stock": sum(vaccine.quantity for vaccine in vaccines),
            "low_stock_count": sum(
                1 for vaccine in vaccines if vaccine.quantity <= vaccine.minimum_stock
            ),
            "expired_count": sum(1 for vaccine in vaccines if vaccine.expiration_date < today),
        },
    }
    return render(request, "assets/overview.html", context)


@ensure_csrf_cookie
def inventory_portal_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    today = timezone.localdate()
    vaccines = list(Vaccine.objects.all())
    low_stock_count = sum(1 for vaccine in vaccines if vaccine.quantity <= vaccine.minimum_stock)
    expired_count = sum(1 for vaccine in vaccines if vaccine.expiration_date < today)

    context = {
        "user": user,
        "today": today,
        "stats": {
            "total_vaccines": len(vaccines),
            "total_stock": sum(vaccine.quantity for vaccine in vaccines),
            "low_stock_count": low_stock_count,
            "expired_count": expired_count,
        },
    }
    return render(request, "assets/portal.html", context)


@ensure_csrf_cookie
def inventory_forms_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    today = timezone.localdate()
    vaccines = list(
        Vaccine.objects.select_related("supplier", "location")
        .all()
        .order_by("expiration_date", "-created_at")
    )
    suppliers = list(Supplier.objects.all().order_by("name"))
    locations = list(StorageLocation.objects.all().order_by("name"))

    total_vaccines = len(vaccines)
    total_stock = sum(vaccine.quantity for vaccine in vaccines)
    low_stock_count = sum(1 for vaccine in vaccines if vaccine.quantity <= vaccine.minimum_stock)
    expired_count = sum(1 for vaccine in vaccines if vaccine.expiration_date < today)
    near_expiry_count = sum(
        1
        for vaccine in vaccines
        if today <= vaccine.expiration_date <= today + timedelta(days=30)
    )

    recent_imports = list(
        StockImport.objects.select_related("vaccine", "supplier")
        .all()
        .order_by("-created_at")[:5]
    )
    recent_exports = list(
        StockExport.objects.select_related("vaccine")
        .all()
        .order_by("-created_at")[:5]
    )
    recent_adjustments = list(
        StockAdjustment.objects.select_related("vaccine")
        .all()
        .order_by("-created_at")[:5]
    )

    recent_transactions = sorted(
        [
            {
                "type": "import",
                "label": "Nhap kho",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.supplier.name if item.supplier else "Khong ro nha cung cap",
                "created_at": item.created_at,
            }
            for item in recent_imports
        ]
        + [
            {
                "type": "export",
                "label": "Xuat kho",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.destination,
                "created_at": item.created_at,
            }
            for item in recent_exports
        ]
        + [
            {
                "type": "adjustment",
                "label": "Dieu chinh",
                "vaccine_name": item.vaccine.name,
                "quantity": item.quantity,
                "meta": item.reason,
                "created_at": item.created_at,
            }
            for item in recent_adjustments
        ],
        key=lambda entry: entry["created_at"],
        reverse=True,
    )[:8]

    page_error = ""
    page_success = ""

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_supplier":
            serializer = SupplierSerializer(data=request.POST)
            if serializer.is_valid():
                serializer.save()
                page_success = "Da tao nha cung cap."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the tao nha cung cap."

        elif action == "create_location":
            serializer = StorageLocationSerializer(data=request.POST)
            if serializer.is_valid():
                serializer.save()
                page_success = "Da tao vi tri bao quan."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the tao vi tri bao quan."

        elif action == "create_vaccine":
            serializer = VaccineSerializer(data=request.POST)
            if serializer.is_valid():
                serializer.save()
                page_success = "Da tao lo vac xin."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the tao lo vac xin."

        elif action == "import_stock":
            serializer = StockImportSerializer(data=request.POST)
            if serializer.is_valid():
                with transaction.atomic():
                    stock_import = serializer.save(created_by=user)
                    stock_import.vaccine.quantity += stock_import.quantity
                    stock_import.vaccine.save(update_fields=["quantity"])
                page_success = "Da ghi nhan phieu nhap."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the nhap kho."

        elif action == "export_stock":
            serializer = StockExportSerializer(data=request.POST)
            if serializer.is_valid():
                vaccine = serializer.validated_data["vaccine"]
                export_quantity = serializer.validated_data["quantity"]
                if vaccine.quantity < export_quantity:
                    page_error = (
                        f"Ton kho khong du. Hien co: {vaccine.quantity}, yeu cau xuat: {export_quantity}."
                    )
                else:
                    with transaction.atomic():
                        stock_export = serializer.save(created_by=user)
                        vaccine = stock_export.vaccine
                        vaccine.quantity -= stock_export.quantity
                        vaccine.save(update_fields=["quantity"])
                    page_success = "Da ghi nhan phieu xuat."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the xuat kho."

        elif action == "adjust_stock":
            serializer = StockAdjustmentSerializer(data=request.POST)
            if serializer.is_valid():
                vaccine = serializer.validated_data["vaccine"]
                adjustment_type = serializer.validated_data["adjustment_type"]
                adjustment_quantity = serializer.validated_data["quantity"]
                if adjustment_type == "decrease" and vaccine.quantity < adjustment_quantity:
                    page_error = f"Ton kho khong du de giam. Hien co: {vaccine.quantity}."
                else:
                    with transaction.atomic():
                        adjustment = serializer.save(created_by=user)
                        vaccine = adjustment.vaccine
                        if adjustment.adjustment_type == "increase":
                            vaccine.quantity += adjustment.quantity
                        else:
                            vaccine.quantity -= adjustment.quantity
                        vaccine.save(update_fields=["quantity"])
                    page_success = "Da ghi nhan dieu chinh kho."
            else:
                page_error = _flatten_serializer_errors(serializer) or "Khong the dieu chinh kho."

        vaccines = list(
            Vaccine.objects.select_related("supplier", "location")
            .all()
            .order_by("expiration_date", "-created_at")
        )
        suppliers = list(Supplier.objects.all().order_by("name"))
        locations = list(StorageLocation.objects.all().order_by("name"))

    filtered_vaccines = _apply_inventory_filters(request, vaccines, today)

    context = {
        "user": user,
        "today": today,
        "page_error": page_error,
        "page_success": page_success,
        "summary": {
            "total_vaccines": total_vaccines,
            "total_stock": total_stock,
            "low_stock_count": low_stock_count,
            "expired_count": expired_count,
            "near_expiry_count": near_expiry_count,
        },
        "vaccines": filtered_vaccines,
        "suppliers": suppliers,
        "locations": locations,
        "recent_transactions": recent_transactions,
        "filter_keyword": request.GET.get("q", ""),
        "filter_status": request.GET.get("status", ""),
        "filter_supplier": request.GET.get("supplier", ""),
        "filter_location": request.GET.get("location", ""),
    }
    return render(request, "assets/forms.html", context)


@ensure_csrf_cookie
def inventory_interface_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    return render(request, "assets/interface.html", {"user": user})


@ensure_csrf_cookie
def supplier_management_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    suppliers = list(Supplier.objects.all().order_by("name"))
    context = {
        "user": user,
        "suppliers": suppliers,
        "supplier_count": len(suppliers),
    }
    return render(request, "assets/suppliers.html", context)


@ensure_csrf_cookie
def location_management_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    locations = list(StorageLocation.objects.all().order_by("name"))
    context = {
        "user": user,
        "locations": locations,
        "location_count": len(locations),
    }
    return render(request, "assets/locations.html", context)


class SupplierViewSet(CsrfProtectedModelViewSet):
    queryset = Supplier.objects.all().order_by("-created_at")
    serializer_class = SupplierSerializer
    permission_classes = [CanReadVaccineStock]


class StorageLocationViewSet(CsrfProtectedModelViewSet):
    queryset = StorageLocation.objects.all().order_by("-created_at")
    serializer_class = StorageLocationSerializer
    permission_classes = [CanReadVaccineStock]


class VaccineViewSet(CsrfProtectedModelViewSet):
    queryset = Vaccine.objects.select_related("supplier", "location").all().order_by("-created_at")
    serializer_class = VaccineSerializer
    permission_classes = [CanReadVaccineStock]


class StockImportViewSet(CsrfProtectedModelViewSet):
    queryset = StockImport.objects.select_related("vaccine", "supplier", "created_by").all().order_by("-created_at")
    serializer_class = StockImportSerializer
    permission_classes = [IsAdminOrReadOnly]

    @transaction.atomic
    def perform_create(self, serializer):
        user = User.objects.filter(id=self.request.session.get("user_id")).first()
        stock_import = serializer.save(created_by=user)
        _apply_stock_import(stock_import)

    @transaction.atomic
    def perform_update(self, serializer):
        old_import = StockImport.objects.get(pk=serializer.instance.pk)
        stock_import = serializer.save()
        _apply_stock_import(old_import, direction=-1)
        _apply_stock_import(stock_import)

    @transaction.atomic
    def perform_destroy(self, instance):
        _apply_stock_import(instance, direction=-1)
        instance.delete()


class StockExportViewSet(CsrfProtectedModelViewSet):
    queryset = StockExport.objects.select_related("vaccine", "created_by").all().order_by("-created_at")
    serializer_class = StockExportSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            user = User.objects.filter(id=self.request.session.get("user_id")).first()
            stock_export = serializer.save(created_by=user)
            _apply_stock_export(stock_export)

    @transaction.atomic
    def perform_update(self, serializer):
        old_export = StockExport.objects.get(pk=serializer.instance.pk)
        stock_export = serializer.save()
        _apply_stock_export(old_export, direction=-1)
        _apply_stock_export(stock_export)

    @transaction.atomic
    def perform_destroy(self, instance):
        _apply_stock_export(instance, direction=-1)
        instance.delete()


class StockAdjustmentViewSet(CsrfProtectedModelViewSet):
    queryset = StockAdjustment.objects.select_related("vaccine", "created_by").all().order_by("-created_at")
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            user = User.objects.filter(id=self.request.session.get("user_id")).first()
            adjustment = serializer.save(created_by=user)
            _apply_stock_adjustment(adjustment)

    @transaction.atomic
    def perform_update(self, serializer):
        old_adjustment = StockAdjustment.objects.get(pk=serializer.instance.pk)
        adjustment = serializer.save()
        _apply_stock_adjustment(old_adjustment, direction=-1)
        _apply_stock_adjustment(adjustment)

    @transaction.atomic
    def perform_destroy(self, instance):
        _apply_stock_adjustment(instance, direction=-1)
        instance.delete()


class InventoryDashboardAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user_id = request.session.get("user_id")
        if not user_id or not User.objects.filter(
            id=user_id,
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
        ).exists():
            return Response({"detail": "Chỉ Admin mới được truy cập thống kê kho."}, status=403)

        today = timezone.now().date()

        total_vaccines = Vaccine.objects.count()
        total_stock = Vaccine.objects.aggregate(total=Sum("quantity"))["total"] or 0
        low_stock_count = Vaccine.objects.filter(quantity__lte=models.F("minimum_stock")).count()
        expired_count = Vaccine.objects.filter(expiration_date__lt=today).count()
        near_expiry_count = Vaccine.objects.filter(
            expiration_date__gte=today,
            expiration_date__lte=today + timedelta(days=30),
        ).count()

        return Response(
            {
                "total_vaccines": total_vaccines,
                "total_stock": total_stock,
                "low_stock_count": low_stock_count,
                "expired_count": expired_count,
                "near_expiry_count": near_expiry_count,
            }
        )
