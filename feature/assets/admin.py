from django.contrib import admin
from .models import (
    Supplier,
    StorageLocation,
    Vaccine,
    StockImport,
    StockExport,
    StockAdjustment,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "email", "created_at")
    search_fields = ("name", "phone", "email")


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "created_at")
    search_fields = ("name",)


@admin.register(Vaccine)
class VaccineAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "manufacturer",
        "batch_number",
        "quantity",
        "minimum_stock",
        "expiration_date",
        "supplier",
        "location",
        "is_low_stock",
        "is_expired",
    )
    search_fields = ("name", "manufacturer", "batch_number")
    list_filter = ("manufacturer", "expiration_date", "supplier", "location")


@admin.register(StockImport)
class StockImportAdmin(admin.ModelAdmin):
    list_display = ("id", "vaccine", "quantity", "supplier", "import_date", "created_by")
    search_fields = ("vaccine__name", "supplier__name")
    list_filter = ("import_date", "supplier")


@admin.register(StockExport)
class StockExportAdmin(admin.ModelAdmin):
    list_display = ("id", "vaccine", "quantity", "destination", "export_date", "created_by")
    search_fields = ("vaccine__name", "destination")
    list_filter = ("export_date",)


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("id", "vaccine", "adjustment_type", "quantity", "reason", "created_by", "created_at")
    search_fields = ("vaccine__name", "reason")
    list_filter = ("adjustment_type", "created_at")