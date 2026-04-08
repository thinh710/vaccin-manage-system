from datetime import timedelta

from django.db import models, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from feature.authentication.models import User
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


def inventory_interface_page(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if not _can_manage_inventory(user):
        return redirect("/users/dashboard/")

    return render(request, "assets/interface.html", {"user": user})


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


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by("-created_at")
    serializer_class = SupplierSerializer
    permission_classes = [CanReadVaccineStock]


class StorageLocationViewSet(viewsets.ModelViewSet):
    queryset = StorageLocation.objects.all().order_by("-created_at")
    serializer_class = StorageLocationSerializer
    permission_classes = [CanReadVaccineStock]


class VaccineViewSet(viewsets.ModelViewSet):
    queryset = Vaccine.objects.select_related("supplier", "location").all().order_by("-created_at")
    serializer_class = VaccineSerializer
    permission_classes = [CanReadVaccineStock]


class StockImportViewSet(viewsets.ModelViewSet):
    queryset = StockImport.objects.select_related("vaccine", "supplier", "created_by").all().order_by("-created_at")
    serializer_class = StockImportSerializer
    permission_classes = [IsAdminOrReadOnly]

    @transaction.atomic
    def perform_create(self, serializer):
        user = User.objects.filter(id=self.request.session.get("user_id")).first()
        stock_import = serializer.save(created_by=user)
        vaccine = stock_import.vaccine
        vaccine.quantity += stock_import.quantity
        vaccine.save(update_fields=["quantity"])


class StockExportViewSet(viewsets.ModelViewSet):
    queryset = StockExport.objects.select_related("vaccine", "created_by").all().order_by("-created_at")
    serializer_class = StockExportSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            user = User.objects.filter(id=self.request.session.get("user_id")).first()
            stock_export = serializer.save(created_by=user)
            vaccine = stock_export.vaccine
            # Guard: không cho phép tồn kho âm (defense-in-depth ngoài serializer)
            if vaccine.quantity < stock_export.quantity:
                raise drf_serializers.ValidationError(
                    {"detail": f"Tồn kho không đủ. Hiện có: {vaccine.quantity}, yêu cầu xuất: {stock_export.quantity}."}
                )
            vaccine.quantity -= stock_export.quantity
            vaccine.save(update_fields=["quantity"])


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = StockAdjustment.objects.select_related("vaccine", "created_by").all().order_by("-created_at")
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            user = User.objects.filter(id=self.request.session.get("user_id")).first()
            adjustment = serializer.save(created_by=user)
            vaccine = adjustment.vaccine

            if adjustment.adjustment_type == "increase":
                vaccine.quantity += adjustment.quantity
            else:
                # Guard: không cho phép tồn kho âm
                if vaccine.quantity < adjustment.quantity:
                    raise drf_serializers.ValidationError(
                        {"detail": f"Tồn kho không đủ để giảm. Hiện có: {vaccine.quantity}, yêu cầu giảm: {adjustment.quantity}."}
                    )
                vaccine.quantity -= adjustment.quantity

            vaccine.save(update_fields=["quantity"])


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
